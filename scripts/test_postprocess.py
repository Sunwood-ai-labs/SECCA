"""Behavior checks for offline postprocessing without model or FreeCAD calls."""

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cad_artifacts
import sandbox_postprocess as post


class PostprocessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve() / "trial"
        (self.root / "workspace").mkdir(parents=True)
        (self.root / "evidence").mkdir()
        self.protocol = post.read_json(post.ASSETS / "protocol.json")
        (self.root / "protocol.json").write_bytes((post.ASSETS / "protocol.json").read_bytes())
        self.manifest = {
            "schema_version": 2, "protocol_id": self.protocol["id"],
            "protocol_sha256": post.digest(self.root / "protocol.json"),
            "sandbox": {"backend": "podman-network-none-uds", "connection": "fixture",
                        "image_id": "sha256:" + "a" * 64}}
        post.write_json(self.root / "trial.json", self.manifest)
        post.write_json(self.root / "evidence/run.json", {"status": "completed", "candidate_stopped": True})
        for name in post.OUTPUTS:
            (self.root / "workspace" / name).write_bytes(("fixture " + name).encode())

    def tearDown(self):
        self.temp.cleanup()

    def job(self, operation="inspect"):
        return post.PostprocessJob.load(self.root, operation)

    def test_rejects_host_trial_and_mutable_image(self):
        for sandbox in ({}, {**self.manifest["sandbox"], "image_id": "runtime:latest"}):
            self.manifest["sandbox"] = sandbox
            post.write_json(self.root / "trial.json", self.manifest)
            with self.assertRaises(ValueError):
                self.job()

    def test_rejects_nonterminal_and_changed_render_spec(self):
        post.write_json(self.root / "evidence/run.json", {"status": "running"})
        with self.assertRaisesRegex(ValueError, "not terminal"):
            self.job()
        post.write_json(self.root / "evidence/run.json", {"status": "completed", "candidate_stopped": True})
        (self.root / "render-spec.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "specification"):
            self.job()

    def test_terminal_status_does_not_prove_candidate_was_stopped(self):
        post.write_json(self.root / "evidence/run.json", {"status": "completed"})
        with self.assertRaisesRegex(ValueError, "not terminal"):
            self.job()

    def test_refuses_linked_cad(self):
        path = self.root / "workspace" / post.OUTPUTS[0]
        source = self.root / "outside"
        path.rename(source)
        try:
            path.symlink_to(source)
        except OSError:
            path.hardlink_to(source)
        with self.assertRaisesRegex(ValueError, "Linked|unlinked"):
            self.job()

    def test_staging_allowlist_excludes_management_and_other_trials(self):
        (self.root / "workspace" / "forbidden.txt").write_text("secret")
        (self.root / "rubric.json").write_text("score secret")
        job = self.job()
        stage = Path(self.temp.name) / "staged"
        stage.mkdir()
        paths = post.prepare_inputs(job, stage)
        actual = {path.relative_to(stage).as_posix() for path in paths}
        self.assertEqual(actual, {
            "protocol.json", "trial.json", "render-spec.json", "evidence/run.json",
            "request.json", "inspect.py", "runtime/freecad_worker.py", "runtime/gui_lease.py",
            "workspace/racing-kart.FCStd", "workspace/racing-kart.step"})
        reduced = post.read_json(stage / "trial.json")
        self.assertEqual(set(reduced), {"protocol_id", "protocol_sha256"})
        self.assertEqual(post.read_json(stage / "evidence/run.json"), {"status": "completed"})

    def test_source_change_between_validation_and_staging_is_rejected(self):
        job = self.job()
        (self.root / "workspace" / post.OUTPUTS[0]).write_bytes(b"changed")
        stage = Path(self.temp.name) / "staged"
        stage.mkdir()
        with self.assertRaisesRegex(ValueError, "changed while copying"):
            post.prepare_inputs(job, stage)

    def test_evidence_paths_normalized_without_changing_hash_or_bytes(self):
        original = {"native": {"file_before": {"path": "/job/workspace/racing-kart.FCStd",
                     "sha256": "abc", "bytes": 7}}, "images": [{"path": "/job/renders/top.png"}]}
        actual = post.normalize_paths(original)
        self.assertEqual(actual["native"]["file_before"],
                         {"path": "workspace/racing-kart.FCStd", "sha256": "abc", "bytes": 7})
        with self.assertRaises(ValueError):
            post.normalize_paths({"path": "/job/../outside"})

    def test_result_requires_this_request_and_original_cad_hashes(self):
        job = self.job()
        result = {"request_id": job.request_id}
        for kind, name in (("native", post.OUTPUTS[0]), ("step", post.OUTPUTS[1])):
            result[kind] = {"file_before": deepcopy(job.sources[name]),
                            "file_after": deepcopy(job.sources[name])}
        post.validate_result(job, result)
        result["native"]["file_after"]["sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "copy hash"):
            post.validate_result(job, result)

    def test_failed_or_unexpected_render_outputs_cannot_be_exported(self):
        job = self.job("render")
        self.assertEqual(post.output_files(job, {"success": False}), [])
        with self.assertRaisesRegex(ValueError, "fixed output"):
            post.output_files(job, {"success": True, "images": {"top": {"path": "/etc/passwd"}}})

    @staticmethod
    def inspection(image):
        return {"Image": image, "Config": {"User": "10000:10000"},
                "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True,
                    "Privileged": False, "CapAdd": [], "CapDrop": ["ALL"],
                    "SecurityOpt": ["no-new-privileges"], "PidMode": "", "IpcMode": "private",
                    "Devices": [], "PortBindings": {}},
                "Mounts": [], "NetworkSettings": {"Ports": {}, "Networks": {}}}

    def test_effective_container_rejects_mounts_network_privileges_and_ports(self):
        job = self.job()
        good = self.inspection(job.image_id)
        post.verify_container(good, job.image_id)
        mutations = [
            lambda info: info["Mounts"].append({"Type": "bind", "Source": "/host"}),
            lambda info: info["HostConfig"].update(NetworkMode="host"),
            lambda info: info["HostConfig"].update(Privileged=True),
            lambda info: info["HostConfig"].update(ReadonlyRootfs=False),
            lambda info: info["Config"].update(User="0"),
            lambda info: info["HostConfig"].update(PortBindings={"9875/tcp": [{}]}),
            lambda info: info["NetworkSettings"].update(Networks={"bridge": {}}),
        ]
        for mutation in mutations:
            changed = deepcopy(good)
            mutation(changed)
            with self.assertRaises(ValueError):
                post.verify_container(changed, job.image_id)

    def test_podman_image_digest_prefix_is_optional_but_identity_is_fixed(self):
        image = self.job().image_id
        for actual in (image, image.removeprefix("sha256:")):
            post.verify_container(self.inspection(actual), image)
        with self.assertRaisesRegex(ValueError, "isolation"):
            post.verify_container(self.inspection("b" * 64), image)

    def test_gui_launcher_and_embedded_sync_code_are_both_valid_python(self):
        class FakeRPC:
            def __init__(self):
                self.calls = []

            def execute_code(self, code):
                compile(code, "gui-worker-code", "exec")
                self.calls.append(code)
                return {"success": True}

        rpc = FakeRPC()
        with patch("xmlrpc.client.ServerProxy", return_value=rpc) as proxy:
            exec(compile(post.GUI_RENDER, "gui-launcher", "exec"), {})
        proxy.assert_called_once_with("http://127.0.0.1:9875")
        self.assertEqual(len(rpc.calls), 1)
        self.assertIn("\nresult = runpy.run_path", rpc.calls[0])
        self.assertIn("['render_saved']('/job/request.json')", rpc.calls[0])

    def test_bounded_capture_preserves_successful_binary_streams(self):
        code = "import os; os.write(1, b'out\\x00\\xff'); os.write(2, b'err\\xfe')"
        result = post.bounded_capture([sys.executable, "-c", code], timeout=5, budget=4096)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"out\x00\xff")
        self.assertEqual(result.stderr, b"err\xfe")
        self.assertIsNone(result.stopped_reason)

    def test_bounded_capture_drains_both_streams_with_one_combined_limit(self):
        code = (
            "import os, threading; "
            "f=lambda fd: [os.write(fd, b'x'*4096) for _ in range(1000)]; "
            "a=threading.Thread(target=f,args=(1,)); b=threading.Thread(target=f,args=(2,)); "
            "a.start(); b.start(); a.join(); b.join()")
        result = post.bounded_capture([sys.executable, "-c", code], timeout=5, budget=8192)
        self.assertEqual(result.stopped_reason, "output_limit")
        self.assertLessEqual(len(result.stdout) + len(result.stderr), 8192)

    def test_bounded_capture_kills_timeout_and_marks_incomplete_output(self):
        code = "import os, time; os.write(2,b'waiting'); time.sleep(30)"
        result = post.bounded_capture([sys.executable, "-c", code], timeout=0.5, budget=4096)
        self.assertEqual(result.stopped_reason, "timeout")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"waiting")

    def test_capture_limit_error_records_truncation_and_cleans_own_container(self):
        job = self.job()
        container = post.OfflineContainer(job)
        identifier = "f" * 64
        container.container_id = identifier
        failed = post.CommandOutput(-1, b"partial stdout", b"partial stderr", "output_limit")
        removed = post.CommandOutput(0, b"", b"")
        with patch.object(post, "bounded_capture", side_effect=[failed, removed]) as capture:
            with self.assertRaisesRegex(RuntimeError, "raw log truncated"):
                with container:
                    pass
        self.assertTrue(container.log[0]["raw_log_truncated"])
        self.assertEqual(container.log[0]["stopped_reason"], "output_limit")
        self.assertEqual(capture.call_args_list[-1].args[0][-3:], ["rm", "--force", identifier])

    def test_successful_inspect_and_render_preserve_outputs_and_source_hashes(self):
        for operation in ("inspect", "render"):
            with self.subTest(operation=operation):
                job = self.job(operation)
                records = deepcopy(job.sources)
                for record in records.values():
                    record["path"] = "/job/" + record["path"]
                result = {"request_id": job.request_id, "success": True}
                exported = {}
                if operation == "inspect":
                    for kind, name in (("native", post.OUTPUTS[0]), ("step", post.OUTPUTS[1])):
                        result[kind] = {"file_before": records[name], "file_after": records[name]}
                else:
                    result.update(source_before=records, source_after=records, source_unchanged=True,
                                  render_spec={"sha256": job.protocol["render_spec_sha256"]}, images={})
                    expected = {item["id"]: item for item in job.spec["views"]}
                    expected["preview"] = job.spec["preview"]
                    for view_id, spec in expected.items():
                        payload = b"PNG-fixture-" + view_id.encode()
                        relative = "renders/" + spec["filename"]
                        exported[relative] = payload
                        result["images"][view_id] = {
                            "path": "/job/" + relative, "exists": True, "bytes": len(payload),
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "width": spec["width"], "height": spec["height"]}
                    review = "evidence/review/review-" + "1" * 32 + ".FCStd"
                    exported[review] = (self.root / "workspace" / post.OUTPUTS[0]).read_bytes()
                    result["review_copy"] = {**job.sources[post.OUTPUTS[0]], "path": "/job/" + review}

                container = post.OfflineContainer(job)
                container.inspection = self.inspection(job.image_id)

                def download(remote, destination, _limit):
                    if remote == "/job/evidence/" + job.result_name:
                        post.write_json(destination, result)
                    else:
                        destination.write_bytes(exported[remote.removeprefix("/job/")])
                    return destination

                with patch.object(post, "OfflineContainer", return_value=container), \
                        patch.object(type(container), "__enter__", return_value=container), \
                        patch.object(container, "upload"), \
                        patch.object(container, "exec", return_value=post.CommandOutput(0, b"", b"")), \
                        patch.object(container, "download", side_effect=download):
                    actual = post.run_postprocess(job)
                self.assertTrue(actual["success"])
                self.assertTrue(actual["host_source_unchanged"])
                self.assertEqual(post.source_records(self.root), job.sources)
                for relative, payload in exported.items():
                    self.assertEqual((self.root / relative).read_bytes(), payload)
                if operation == "render":
                    self.assertEqual(actual["source_before"], job.sources)

    def test_container_cleanup_after_start_failure_uses_only_own_id(self):
        job = self.job()
        identifier = "d" * 64
        calls = []

        def fake(_container, *args, **_kwargs):
            calls.append(args)
            if args[0] == "create":
                return subprocess.CompletedProcess(args, 0, (identifier + "\n").encode(), b"")
            if args[0] == "inspect":
                return subprocess.CompletedProcess(args, 0,
                    json.dumps([self.inspection(job.image_id)]).encode(), b"")
            if args[0] == "start":
                raise RuntimeError("synthetic failed startup")
            return subprocess.CompletedProcess(args, 0, b"", b"")

        with patch.object(post.OfflineContainer, "podman", fake):
            with self.assertRaisesRegex(RuntimeError, "synthetic"):
                with post.OfflineContainer(job):
                    pass
        self.assertEqual(calls[-1], ("rm", "--force", identifier))
        create = calls[0]
        self.assertNotIn("--volume", create)
        self.assertNotIn("--mount", create)
        self.assertIn("--read-only", create)
        self.assertIn("none", create)

    def test_failure_preserves_host_cad_and_writes_failure_evidence(self):
        job = self.job()
        with patch.object(post.OfflineContainer, "__enter__", side_effect=RuntimeError("synthetic")):
            with self.assertRaisesRegex(RuntimeError, "Offline postprocessing failed"):
                post.run_postprocess(job)
        result = post.read_json(self.root / "evidence/validation.json")
        self.assertFalse(result["success"])
        self.assertTrue(result["host_source_unchanged"])
        self.assertFalse(result["sandbox"]["api_channel"])
        self.assertEqual(post.source_records(self.root), job.sources)

    def test_cleanup_failure_does_not_claim_success_or_lose_container_id(self):
        container = post.OfflineContainer(self.job())
        container.container_id = "e" * 64
        with patch.object(container, "podman", return_value=subprocess.CompletedProcess([], 1, b"", b"busy")):
            container.cleanup()
        self.assertIn("Failed to remove", container.cleanup_error)
        self.assertEqual(container.container_id, "e" * 64)

    def test_legacy_host_execution_paths_fail_closed(self):
        args = argparse.Namespace(trial=str(self.root), timeout=180, freecadcmd="freecadcmd")
        with self.assertRaisesRegex(ValueError, "Host FreeCAD"):
            cad_artifacts.inspect(args)
        with self.assertRaisesRegex(ValueError, "disabled"):
            cad_artifacts.render_code(args)


if __name__ == "__main__":
    unittest.main()

