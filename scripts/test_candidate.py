"""Contract and real-child fixtures. Never invokes Podman, FreeCAD or models."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import candidate
import sandbox_runner as runner
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "container"))
import candidate_entry

IMAGE = "sha256:" + "a" * 64


class FixturePodman:
    def __init__(self, child):
        self.prefix = [sys.executable, str(child)]
        self.calls, self.volumes = [], {}

    def call(self, args, **kwargs):
        self.calls.append(args)
        output = b""
        if args[:2] == ["volume", "create"]:
            self.volumes[args[-1].rsplit("-", 1)[-1]] = args[-1]
        if args[0] == "create":
            output = b"gateway-id" if any("-gateway" in arg for arg in args) else b"candidate-id"
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr=b"")

    def document(self, args):
        if args[0] == "image":
            return [{"Id": IMAGE}]
        return [{"Id": args[1], "Image": IMAGE, "EffectiveCaps": [], "State": {"Running": False},
                 "Config": {"User": "10000:10000"}, "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges"]},
                 "Mounts": [{"Type": "volume", "Name": self.volumes[key], "Destination": path, "RW": rw} for key, path, rw in (("work", "/workspace", True), ("home", "/home/candidate", True), ("channel", "/run/model-link", False))]}]


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.package = self.root / "package"
        assets = self.package / "assets"
        assets.mkdir(parents=True)
        self.protocol = candidate.read_json(candidate.PACKAGE / "assets/protocol.json")
        (assets / "reference.jpg").write_bytes(b"synthetic fixture reference")
        self.protocol["reference_image_sha256"] = candidate.sha256(assets / "reference.jpg")
        candidate.write_json_new(assets / "protocol.json", self.protocol)
        candidate.write_json_new(assets / "manifest.json", {"schema_version": 1, "algorithm": "sha256", "files": {p.relative_to(self.package).as_posix(): candidate.sha256(p) for p in assets.iterdir()}})
        self.args = argparse.Namespace(trial=self.root / "trial", model="fixture/exact-free", connection="fixture", image="fixture", api_base_url="https://api.example.org/v1", api_model=None, credential_env=None, timeout=1)
        patcher = patch.object(candidate, "PACKAGE", self.package)
        patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        with patch.object(runner, "api_base", side_effect=lambda value: value), patch.object(runner.Podman, "document", return_value=[{"Id": IMAGE[7:]}]):
            return candidate.prepare(self.args)

    def test_prepare_preserves_exact_input_and_rejects_changed_input(self):
        self.prepare()
        with patch.object(runner, "api_base", side_effect=lambda value: value):
            manifest, _, runtime = candidate.load_trial(self.args.trial)
            self.assertEqual(manifest["sandbox"]["image_id"], IMAGE)
            self.assertEqual(runtime["prompt_text"], self.protocol["prompt_text"])
            self.assertEqual(runtime["model_id"], self.args.model)
            with self.assertRaises(FileExistsError):
                self.prepare()
            (self.args.trial / "runtime-input/runtime.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "changed"):
                candidate.load_trial(self.args.trial)

    def test_legacy_local_trial_fails_closed(self):
        self.args.trial.mkdir()
        candidate.write_json_new(self.args.trial / "trial.json", {"schema_version": 1})
        with self.assertRaisesRegex(ValueError, "OS-isolated"):
            candidate.load_trial(self.args.trial)

    def metadata(self):
        return {"provider_id": "fixture", "provider_api": self.args.api_base_url,
                "provider_npm": "@ai-sdk/openai-compatible", "source_url": "https://models.dev/api.json",
                "source_sha256": "b" * 64,
                "model": {"id": "exact-free", "name": "Fixture Free", "attachment": False,
                          "reasoning": True, "tool_call": True,
                          "modalities": {"input": ["text"], "output": ["text"]},
                          "provider": {"api": "https://must-not-configure.example/v1"},
                          "options": {"baseURL": "https://must-not-configure.example/v1"},
                          "description": "source-only description"}}

    def prepare_metadata(self, metadata=None):
        self.args.model_metadata = self.root / "source-model.json"
        candidate.write_json_new(self.args.model_metadata, metadata or self.metadata())
        return self.prepare()

    def test_metadata_snapshot_preserves_text_only_and_filters_provider_overrides(self):
        self.prepare_metadata()
        with patch.object(runner, "api_base", side_effect=lambda value: value):
            manifest, _, runtime = candidate.load_trial(self.args.trial)
        snapshot = self.args.trial / "runtime-input/model-metadata.json"
        self.assertEqual(snapshot.read_bytes(), self.args.model_metadata.read_bytes())
        self.assertEqual(manifest["file_hashes"]["runtime-input/model-metadata.json"], candidate.sha256(snapshot))
        self.assertTrue(any("catalog metadata" in value for value in manifest["protocol_deviations"]))
        model = candidate_entry.model_configuration(candidate.read_json(snapshot), runtime["model_id"], runtime["api_model_id"])
        self.assertIs(model["attachment"], False)
        self.assertEqual(model["modalities"], {"input": ["text"], "output": ["text"]})
        self.assertEqual(model["id"], "exact-free")
        self.assertFalse({"provider", "api", "npm", "env", "options", "description"} & set(model))
        self.assertEqual(runtime["api_base_url"], "http://127.0.0.1:18080/v1")

    def test_metadata_tampering_and_unmanifested_file_are_rejected(self):
        self.prepare_metadata()
        snapshot = self.args.trial / "runtime-input/model-metadata.json"
        snapshot.write_text("{}")
        with self.assertRaisesRegex(ValueError, "changed"):
            candidate.load_trial(self.args.trial)
        manifest_path = self.args.trial / "trial.json"
        manifest = candidate.read_json(manifest_path)
        del manifest["model_metadata"]
        del manifest["file_hashes"]["runtime-input/model-metadata.json"]
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "Unmanifested"):
            candidate.load_trial(self.args.trial)

    def test_metadata_identity_and_provenance_are_checked(self):
        for field, value in (("provider_id", "other"), ("provider_api", "https://other.example/v1"),
                             ("source_sha256", "not-a-sha")):
            metadata = self.metadata()
            metadata[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                runner.validate_model_metadata(metadata, self.args.model, "exact-free", self.args.api_base_url)
        metadata = self.metadata()
        metadata["model"]["id"] = "different-native-id"
        for validator in (lambda: runner.validate_model_metadata(metadata, self.args.model, "exact-free", self.args.api_base_url),
                          lambda: candidate_entry.model_configuration(metadata, self.args.model, "exact-free"),
                          lambda: candidate_entry.model_configuration(self.metadata(), self.args.model, "different-native-id")):
            with self.assertRaisesRegex(ValueError, "identity"):
                validator()

    def test_rehashed_metadata_still_must_match_manifest_model(self):
        self.prepare_metadata()
        snapshot = self.args.trial / "runtime-input/model-metadata.json"
        metadata = candidate.read_json(snapshot)
        metadata["model"]["id"] = "other"
        snapshot.write_text(json.dumps(metadata))
        manifest_path = self.args.trial / "trial.json"
        manifest = candidate.read_json(manifest_path)
        manifest["file_hashes"]["runtime-input/model-metadata.json"] = candidate.sha256(snapshot)
        manifest_path.write_text(json.dumps(manifest))
        with patch.object(runner, "api_base", side_effect=lambda value: value), self.assertRaisesRegex(ValueError, "identity"):
            candidate.load_trial(self.args.trial)

    def test_credential_value_never_written_to_prepared_inputs(self):
        self.args.credential_env = "FIXTURE_KEY"
        with patch.dict(os.environ, {"FIXTURE_KEY": "never-record-fixture-value"}):
            self.prepare()
        for path in self.args.trial.rglob("*"):
            if path.is_file():
                self.assertNotIn(b"never-record-fixture-value", path.read_bytes())
        with self.assertRaises(ValueError):
            candidate.credential_names(["HOME"])

    def synthetic_run(self, body, with_outputs=False):
        self.prepare()
        child = self.root / "attach.py"
        child.write_text(body)
        client = FixturePodman(child)
        def collect(*args):
            if with_outputs:
                args[4].write_bytes(b"synthetic output, validity is checked separately")
            return with_outputs
        with patch.object(runner, "api_base", side_effect=lambda value: value), patch.object(runner, "Podman", return_value=client), patch.object(runner, "collect_artifact", side_effect=collect):
            result = candidate.run(argparse.Namespace(trial=self.args.trial))
        return result, candidate.read_json(self.args.trial / "evidence/run.json"), client

    def test_real_child_attach_records_raw_output_failure_and_single_use(self):
        result, meta, _ = self.synthetic_run("import sys\nprint('{\"type\":\"sandbox_generation_start\"}',flush=True)\nprint('{\"type\":\"error\",\"error\":\"fixture\"}',flush=True)\nsys.stderr.buffer.write(b'fixture stderr\\r\\n')\nsys.exit(7)\n")
        self.assertEqual((result, meta["status"], meta["returncode"]), (1, "failed", 7))
        self.assertTrue(meta["candidate_stopped"])
        self.assertEqual((self.args.trial / "evidence/stderr.log").read_bytes(), b"fixture stderr\r\n")
        before = (self.args.trial / "evidence/run.json").read_bytes()
        with patch.object(runner, "api_base", side_effect=lambda value: value), self.assertRaises(FileExistsError):
            candidate.run(argparse.Namespace(trial=self.args.trial))
        self.assertEqual((self.args.trial / "evidence/run.json").read_bytes(), before)

    def test_real_child_timeout_requests_container_kill(self):
        result, meta, client = self.synthetic_run("import time\nprint('{\"type\":\"sandbox_generation_start\"}',flush=True)\ntime.sleep(30)\n")
        self.assertEqual((result, meta["status"]), (1, "timeout"))
        self.assertIn(["kill", "candidate-id"], client.calls)

    def test_metrics_keep_internal_tool_errors(self):
        metrics = candidate.RunMetrics()
        metrics.observe(json.dumps({"type": "tool_use", "part": {"tool": "freecad", "state": {"status": "completed", "output": "Failed to execute code: fixture"}}}))
        self.assertEqual(metrics.errors[0]["type"], "tool_output_error")

    def test_zero_exit_with_missing_outputs_is_failed(self):
        result, meta, _ = self.synthetic_run("print('{\"type\":\"sandbox_generation_start\"}',flush=True)\nprint('{\"type\":\"error\",\"error\":\"ModelNotFound\"}',flush=True)\n")
        self.assertEqual((result, meta["status"], meta["returncode"]), (1, "failed", 0))
        self.assertEqual(meta["missing_outputs"], ["racing-kart.FCStd", "racing-kart.step"])

    def test_transient_error_with_both_outputs_remains_completed(self):
        result, meta, _ = self.synthetic_run("print('{\"type\":\"sandbox_generation_start\"}',flush=True)\nprint('{\"type\":\"error\",\"error\":\"transient\"}',flush=True)\n", with_outputs=True)
        self.assertEqual((result, meta["status"]), (0, "completed"))
        self.assertEqual(meta["metrics"]["errors"][0]["type"], "error")


class CapabilityTests(unittest.TestCase):
    def record(self):
        client = FixturePodman("unused")
        client.volumes = {"work": "work", "home": "home", "channel": "channel"}
        record = client.document(["inspect", "fixture"])[0]
        record["EffectiveCaps"] = None
        record["BoundingCaps"] = None
        record["HostConfig"]["CapDrop"] = ["CAP_" + value for value in runner.PODMAN_DEFAULT_CAPS]
        return record, client.volumes

    def test_podman_expanded_default_capabilities_with_null_runtime_fields_are_accepted(self):
        record, volumes = self.record()
        runner.validate_candidate(record, volumes)

    def test_incomplete_drop_list_and_reported_remaining_capabilities_are_rejected(self):
        for mutation in (lambda r: r["HostConfig"].update(CapDrop=["CAP_CHOWN"]),
                         lambda r: r.update(EffectiveCaps=["CAP_CHOWN"]),
                         lambda r: r.update(BoundingCaps=["CAP_CHOWN"]),
                         lambda r: r["HostConfig"].update(CapAdd=["CAP_CHOWN"])):
            record, volumes = self.record()
            mutation(record)
            with self.assertRaises(ValueError):
                runner.validate_candidate(record, volumes)

    def test_actual_process_requires_all_capability_sets_zero_and_nnp(self):
        fields = {"CapEff": "0000000000000000", "CapPrm": "0000000000000000", "CapBnd": "0000000000000000", "NoNewPrivs": "1"}
        def status(values):
            return "\n".join(key + ":\t" + value for key, value in values.items())
        self.assertEqual(candidate_entry.validate_process_security(status(fields)), fields)
        for key in fields:
            changed = dict(fields)
            changed[key] = "0" if key == "NoNewPrivs" else "0000000000000001"
            with self.subTest(key=key), self.assertRaises(ValueError):
                candidate_entry.validate_process_security(status(changed))
        with self.assertRaises(ValueError):
            candidate_entry.validate_process_security("CapEff:\t0\nNoNewPrivs:\t1")


class ArtifactTests(unittest.TestCase):
    def archive(self, kind=tarfile.REGTYPE, name="racing-kart.FCStd"):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as archive:
            member = tarfile.TarInfo(name)
            member.type, member.size = kind, 3 if kind == tarfile.REGTYPE else 0
            member.linkname = "/host-secret" if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE) else ""
            archive.addfile(member, io.BytesIO(b"CAD") if member.size else None)
        return data.getvalue()

    def test_regular_artifact_preserves_exact_bytes(self):
        self.assertEqual(runner.artifact_from_tar(self.archive(), "racing-kart.FCStd"), b"CAD")

    def test_links_devices_directories_and_traversal_are_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.CHRTYPE, tarfile.FIFOTYPE):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                runner.artifact_from_tar(self.archive(kind), "racing-kart.FCStd")
        for name in ("../racing-kart.FCStd", "/racing-kart.FCStd", "other.FCStd"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                runner.artifact_from_tar(self.archive(name=name), "racing-kart.FCStd")


if __name__ == "__main__":
    unittest.main()
