import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import scores


class ScoresTests(unittest.TestCase):
    def setUp(self):
        self.baseline = scores.verify_baseline()
        self.reviews = copy.deepcopy(self.baseline["canonical_comparison_reviews"])
        self.hashes = self.baseline["evidence_hashes"]

    def make_trial(self, folder):
        trial = Path(folder) / "trial"
        for name in ("workspace", "evidence", "renders"):
            (trial / name).mkdir(parents=True, exist_ok=True)
        shutil.copyfile(scores.ASSETS / "reference.jpg", trial / "workspace/reference.jpg")
        shutil.copyfile(scores.ASSETS / "protocol.json", trial / "protocol.json")
        protocol = scores.read_json(trial / "protocol.json")
        protocol_hash = scores.digest(trial / "protocol.json")
        sandbox = {"backend": "podman-network-none-uds", "connection": "score-fixture",
                   "image_id": "sha256:" + "a" * 64}
        scores.write_json(trial / "trial.json", {"schema_version": 2, "sandbox": sandbox,
                                                 "protocol_id": protocol["id"], "protocol_sha256": protocol_hash,
                                                 "file_hashes": {"protocol.json": protocol_hash}})
        scores.write_json(trial / "evidence/run.json", {
            "status": "completed", "candidate_stopped": True, "saved_artifact_replay": True,
            "new_model_inference_performed": False,
            "scope": "Synthetic provenance fixture using existing images and non-native CAD stubs; no model or Podman invocation"})
        sources = {}
        for name in protocol["outputs"]:
            path = trial / "workspace" / name
            path.write_bytes(b"Explicit non-native CAD stub for score provenance tests only.\n")
            sources[name] = {"path": str(path), "exists": True, "bytes": path.stat().st_size, "sha256": scores.digest(path)}
        spec = scores.read_json(scores.ASSETS / "render-spec.json")
        images = {}
        names = dict(zip(scores.VIEWS, ("kart-front-isometric-white.png", "score-top-white.png", "score-right-white.png")))
        for fixed in spec["views"]:
            view = fixed["id"]
            target = trial / f"renders/{view}.png"
            shutil.copyfile(scores.ASSETS / "baseline/evidence" / names[view], target)
            images[view] = {"path": f"renders/{view}.png", "exists": True, "bytes": target.stat().st_size,
                            "sha256": scores.digest(target), "width": fixed["width"], "height": fixed["height"],
                            "camera_type": spec["projection"], "requested_quaternion_xyzw": fixed["quaternion_xyzw"],
                            "actual_quaternion_xyzw": fixed["quaternion_xyzw"]}
        manifest = {"success": True, "source_unchanged": True, "host_source_unchanged": True,
                    "sandbox": {"backend": "podman-offline-postprocess", "connection": sandbox["connection"],
                                "image_id": sandbox["image_id"], "network": "none",
                                "api_channel": False, "bind_mounts": []},
                    "source_before": copy.deepcopy(sources),
                    "source_after": sources, "render_spec": {"sha256": scores.digest(scores.ASSETS / "render-spec.json")},
                    "presentation": {key: spec[key] for key in ("background", "projection", "animation_enabled", "display_mode", "preserve_model_colors", "preserve_model_visibility")},
                    "images": images, "model": "must-not-be-copied"}
        scores.write_json(trial / "evidence/render.json", manifest)
        return trial, manifest

    def reject_render(self, mutate):
        with tempfile.TemporaryDirectory() as folder:
            trial, manifest = self.make_trial(folder)
            mutate(trial, manifest)
            scores.write_json(trial / "evidence/render.json", manifest)
            with self.assertRaises((ValueError, OSError)):
                scores.packet(trial, Path(folder) / "rejected-packet")
            self.assertFalse((Path(folder) / "rejected-packet").exists())

    def reject(self, mutate):
        mutate(self.reviews)
        with self.assertRaises(ValueError):
            scores.aggregate_reviews(self.reviews, self.hashes)

    def test_baseline_actual_43_and_identity_aware_coordinator(self):
        self.assertEqual(self.baseline["score"], 43)
        self.assertEqual(self.baseline["historical_review_totals"], [45, 42, 42])
        self.assertFalse(self.reviews[0]["model_blinded"])
        self.assertFalse(self.reviews[0]["fresh_context"])
        self.assertEqual([c["median"] for c in self.baseline["criteria"]], [13, 13, 8, 4, 5])
        self.assertEqual(self.hashes["rubric"], scores.digest(scores.ASSETS / "baseline/evidence/likeness-rubric-original.json"))
        self.assertEqual(self.baseline["canonical_rubric_sha256"], scores.digest(scores.ASSETS / "rubric.json"))
        self.assertNotEqual(self.hashes["rubric"], self.baseline["canonical_rubric_sha256"])

    def test_failed_or_changed_render_rejected(self):
        for key in ("success", "source_unchanged"):
            for value in (False, None, 1, "true"):
                with self.subTest(key=key, value=value):
                    self.reject_render(lambda t, m: m.update({key: value}))

    def test_trial_requires_schema_2_and_fixed_podman_identity(self):
        def change_prepared(trial, mutate):
            prepared = scores.read_json(trial / "trial.json")
            mutate(prepared)
            scores.write_json(trial / "trial.json", prepared)

        for value in (None, 1, "2", 2.0, True):
            with self.subTest(schema_version=value):
                self.reject_render(lambda t, m: change_prepared(t, lambda p: p.update(schema_version=value)))
        self.reject_render(lambda t, m: change_prepared(t, lambda p: p.pop("sandbox")))
        self.reject_render(lambda t, m: change_prepared(t, lambda p: p.update(sandbox=[])))
        for key, invalid in (("backend", "host"), ("image_id", "runtime:latest"),
                             ("image_id", "a" * 64), ("image_id", "sha256:" + "A" * 64),
                             ("connection", ""), ("connection", "other-connection")):
            with self.subTest(key=key, invalid=invalid):
                self.reject_render(lambda t, m: change_prepared(t, lambda p: p["sandbox"].update({key: invalid})))
        for key in ("backend", "image_id", "connection"):
            with self.subTest(missing=key):
                self.reject_render(lambda t, m: change_prepared(t, lambda p: p["sandbox"].pop(key)))

    def test_terminal_candidate_must_be_explicitly_stopped(self):
        for value in (None, False, 0, 1, "true"):
            with self.subTest(candidate_stopped=value):
                self.reject_render(lambda t, m: scores.write_json(
                    t / "evidence/run.json", {"status": "completed", "candidate_stopped": value}))
        self.reject_render(lambda t, m: scores.write_json(t / "evidence/run.json", {"status": "completed"}))

    def test_render_requires_matching_offline_podman_provenance(self):
        self.reject_render(lambda t, m: m.pop("sandbox"))
        self.reject_render(lambda t, m: m.update(sandbox=[]))
        for key, invalid in (("backend", "host"), ("network", "bridge"),
                             ("api_channel", True), ("api_channel", 0),
                             ("bind_mounts", ["/host"]), ("bind_mounts", None),
                             ("image_id", "sha256:" + "b" * 64),
                             ("connection", "other-connection")):
            with self.subTest(key=key, invalid=invalid):
                self.reject_render(lambda t, m: m["sandbox"].update({key: invalid}))
        for key in ("backend", "network", "api_channel", "bind_mounts", "image_id", "connection"):
            with self.subTest(missing=key):
                self.reject_render(lambda t, m: m["sandbox"].pop(key))
        for value in (None, False, 0, 1, "true"):
            with self.subTest(host_source_unchanged=value):
                self.reject_render(lambda t, m: m.update(host_source_unchanged=value))
        self.reject_render(lambda t, m: m.pop("host_source_unchanged"))

    def test_saved_artifact_replay_remains_explicit_after_packet(self):
        with tempfile.TemporaryDirectory() as folder:
            trial, _ = self.make_trial(folder)
            source = trial / "evidence/run.json"
            before = source.read_bytes()
            result = scores.packet(trial, Path(folder) / "packet")
            self.assertEqual(result["evidence_hashes"]["reference"], self.hashes["reference"])
            self.assertEqual(source.read_bytes(), before)
            run = scores.read_json(source)
            self.assertTrue(run["saved_artifact_replay"])
            self.assertFalse(run["new_model_inference_performed"])

    def test_missing_or_nonterminal_run_rejected(self):
        self.reject_render(lambda t, m: (t / "evidence/run.json").unlink())
        for status in (None, "prepared", "running"):
            with self.subTest(status=status):
                self.reject_render(lambda t, m: scores.write_json(t / "evidence/run.json", {"status": status}))

    def test_missing_or_changed_cad_source_rejected(self):
        for name in ("racing-kart.FCStd", "racing-kart.step"):
            with self.subTest(name=name):
                self.reject_render(lambda t, m: (t / "workspace" / name).unlink())
                self.reject_render(lambda t, m: (t / "workspace" / name).write_bytes(b"changed CAD"))
                for phase in ("source_before", "source_after"):
                    self.reject_render(lambda t, m: m[phase][name].update(sha256="0" * 64))
                    self.reject_render(lambda t, m: m[phase][name].update(path="renders/top.png"))

    def test_render_spec_and_protocol_binding_rejected(self):
        self.reject_render(lambda t, m: m["render_spec"].update(sha256="0" * 64))
        self.reject_render(lambda t, m: scores.write_json(t / "trial.json", {"protocol_sha256": "0" * 64}))

        def changed_protocol(trial, manifest):
            protocol = scores.read_json(trial / "protocol.json")
            protocol["render_spec_sha256"] = "0" * 64
            scores.write_json(trial / "protocol.json", protocol)
            prepared = scores.read_json(trial / "trial.json")
            prepared["protocol_sha256"] = scores.digest(trial / "protocol.json")
            prepared["file_hashes"]["protocol.json"] = prepared["protocol_sha256"]
            scores.write_json(trial / "trial.json", prepared)

        self.reject_render(changed_protocol)

    def test_camera_presentation_and_dimensions_rejected(self):
        for view in scores.VIEWS:
            for field, value in (("camera_type", "Perspective"), ("width", 20), ("height", 20),
                                 ("requested_quaternion_xyzw", [0, 0, 0, 0]),
                                 ("actual_quaternion_xyzw", [0, 0, 0, 0]),
                                 ("actual_quaternion_xyzw", ["nan", 0, 0, 1])):
                with self.subTest(view=view, field=field):
                    self.reject_render(lambda t, m: m["images"][view].update({field: value}))
        for key, value in (("background", "Black"), ("projection", "Perspective"), ("animation_enabled", True),
                           ("display_mode", "Shaded"), ("preserve_model_colors", False), ("preserve_model_visibility", False)):
            with self.subTest(presentation=key):
                self.reject_render(lambda t, m: m["presentation"].update({key: value}))

        def wrong_png_size(trial, manifest):
            path = trial / "renders/top.png"
            data = bytearray(path.read_bytes())
            data[16:20] = (20).to_bytes(4, "big")
            path.write_bytes(data)
            manifest["images"]["top"]["sha256"] = scores.digest(path)

        self.reject_render(wrong_png_size)

    def test_image_paths_must_stay_in_trial(self):
        def outside(trial, manifest):
            path = trial.parent / "outside.png"
            shutil.copyfile(trial / "renders/top.png", path)
            manifest["images"]["top"]["path"] = str(path)

        self.reject_render(outside)

        def traversal(trial, manifest):
            outside(trial, manifest)
            manifest["images"]["top"]["path"] = "../outside.png"

        self.reject_render(traversal)

    def test_equivalent_quaternion_sign_is_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            trial, manifest = self.make_trial(folder)
            for entry in manifest["images"].values():
                for key in ("requested_quaternion_xyzw", "actual_quaternion_xyzw"):
                    entry[key] = [-number for number in entry[key]]
            scores.write_json(trial / "evidence/render.json", manifest)
            self.assertEqual(scores.packet(trial, Path(folder) / "packet")["evidence_hashes"]["rubric"],
                             scores.digest(scores.ASSETS / "rubric.json"))

    def test_missing_and_duplicate_criteria(self):
        self.reject(lambda r: r[1]["criteria"].pop())
        self.setUp()
        self.reject(lambda r: r[1]["criteria"][1].update(id=scores.IDS[0]))

    def test_out_of_range_and_nonfinite_scores(self):
        for value in (-1, 26, float("nan"), float("inf"), True, "12"):
            with self.subTest(value=value):
                reviews = copy.deepcopy(self.reviews)
                reviews[0]["criteria"][0]["score"] = value
                with self.assertRaises(ValueError):
                    scores.aggregate_reviews(reviews, self.hashes)

    def test_wrong_maximum(self):
        self.reject(lambda r: r[2]["criteria"][0].update(max=100))

    def test_duplicate_identity_and_count(self):
        self.reject(lambda r: r[2].update(review_id=r[1]["review_id"]))
        with self.assertRaises(ValueError):
            scores.aggregate_reviews(self.reviews[:2], self.hashes)

    def test_wrong_or_missing_evidence_hash(self):
        self.reject(lambda r: r[1]["evidence_hashes"].update(top="0" * 64))
        self.setUp()
        self.reject(lambda r: r[1]["evidence_hashes"].pop("reference"))

    def test_missing_positive_and_deduction_evidence(self):
        self.reject(lambda r: r[0]["criteria"][0].update(evidence=[]))
        self.setUp()
        self.reject(lambda r: r[0]["criteria"][0].update(evidence=[{"kind": "positive", "observation": "The chassis has four exposed wheels."}]))

    def test_blinding_provenance_and_order(self):
        self.reject(lambda r: r[1].update(fresh_context=False))
        self.setUp()
        self.reject(lambda r: r[2].update(model_blinded=False))
        self.setUp()
        self.reject(lambda r: r[1]["context_provenance"].update(other_reviews_read=True))
        self.setUp()
        self.reject(lambda r: r[0]["context_provenance"].update(recorded_at="2026-10-18T00:00:00Z"))

    def test_packet_and_cli_aggregation_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            trial, manifest = self.make_trial(folder)
            images = manifest["images"]
            packet = Path(folder) / "packet"
            result = scores.packet(trial, packet)
            expected_hashes = {**self.hashes, "rubric": scores.digest(scores.ASSETS / "rubric.json")}
            self.assertEqual(result["evidence_hashes"], expected_hashes)
            self.assertEqual({str(p.relative_to(packet)).replace("\\", "/") for p in packet.rglob("*") if p.is_file()},
                             {"reference.jpg", "renders/isometric.png", "renders/top.png", "renders/right.png", "rubric.json", "review-template.json", "README.txt"})
            self.assertEqual(scores.digest(packet / "renders/top.png"), images["top"]["sha256"])
            self.assertNotIn("must-not-be-copied", "".join(p.read_text(encoding="utf-8") for p in packet.iterdir() if p.suffix in (".json", ".txt")))
            paths = []
            for i, review in enumerate(self.reviews):
                review["evidence_hashes"] = result["evidence_hashes"]
                path = trial / f"review-{i}.json"
                scores.write_json(path, review)
                paths.append(path)
            output = scores.aggregate(trial, paths)
            self.assertEqual(output["score"], 43)
            self.assertTrue(output["cad_validation"]["separate_from_visual_score"])
            self.assertEqual(json.loads((trial / "score.json").read_text())["score"], 43)
            (trial / "renders/top.png").write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                scores.packet(trial, Path(folder) / "altered-packet")


if __name__ == "__main__":
    unittest.main()
