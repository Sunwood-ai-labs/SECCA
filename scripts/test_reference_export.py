"""Historical record publication fixtures with synthetic host identifiers."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from export_reference_records import export, verify_public_export


class ReferenceExportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "private"
        self.output = self.root / "public"
        (self.source / "references/verification").mkdir(parents=True)
        self.output.mkdir()
        self.home = "Q:" + "\\" + "Users" + "\\" + "fixture"
        self.record = self.source / "references/verification/run.json"
        self.record.write_text(json.dumps({"connection": "fixture-connection", "path": self.home + "\\trial.json", "score": 43}), encoding="utf-8")
        self.source_payload = self.record.read_bytes()
        original_hash = hashlib.sha256(self.source_payload).hexdigest()
        (self.source / "references/verified-runtime.json").write_text(json.dumps({"evidence_sha256": original_hash}), encoding="utf-8")

    def test_identifiers_are_replaced_without_changing_result_or_original(self):
        manifest = export(self.source, self.output)
        record = json.loads((self.output / "references/verification/run.json").read_text())
        self.assertEqual(record["score"], 43)
        self.assertEqual(record["connection"], "<PODMAN_CONNECTION>")
        self.assertEqual(record["path"], "<HOST_HOME>\\trial.json")
        self.assertFalse(record["public_export"]["raw_record"])
        self.assertEqual(self.record.read_bytes(), self.source_payload)
        self.assertEqual(len(manifest["files"]), 2)
        self.assertEqual(verify_public_export(self.output)["files"], 2)

    def test_dependent_hashes_refer_to_exported_bytes(self):
        export(self.source, self.output)
        summary = json.loads((self.output / "references/verified-runtime.json").read_text())
        payload = (self.output / "references/verification/run.json").read_bytes()
        self.assertEqual(summary["evidence_sha256"], hashlib.sha256(payload).hexdigest())

    def test_export_is_deterministic_and_detects_later_tampering(self):
        first = export(self.source, self.output)
        self.assertEqual(export(self.source, self.output), first)
        (self.output / "references/verification/run.json").write_text("{}")
        with self.assertRaises(ValueError):
            verify_public_export(self.output)

    def test_source_and_export_cannot_overlap(self):
        for target in (self.source, self.source / "references", self.root):
            with self.subTest(target=target), self.assertRaises(ValueError):
                export(self.source, target)


if __name__ == "__main__":
    unittest.main()
