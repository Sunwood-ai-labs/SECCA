"""Regression checks for public management metadata portability."""
import unittest
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from export_beam import export, portable, verify, verify_portability


class PortableManagementTests(unittest.TestCase):
    def test_named_connection_in_create_command_is_replaced_and_guarded(self):
        original = {"Config": {"CreateCommand": ["podman", "--connection", "private-lab", "create"]},
                    "alternate": ["podman", "--connection=private-lab", "inspect"],
                    "responseHeaders": {"connection": "keep-alive"}}
        exported = portable(original, Path("archive"))
        self.assertEqual(exported["Config"]["CreateCommand"][2], "local-connection")
        self.assertEqual(exported["alternate"][1], "--connection=local-connection")
        self.assertEqual(exported["responseHeaders"], original["responseHeaders"])
        with self.assertRaisesRegex(ValueError, "private connection argv"):
            verify_portability(original, "fixture")
        verify_portability(exported, "fixture")

    def test_private_graph_storage_home_is_replaced_and_guarded(self):
        host = "/home/" + "archived-account"
        original = {"StaticDir": host + "/.local/share/containers/storage/id/userdata",
                    "GraphDriver": {"Data": {"LowerDir": host + "/layer-a:" + host + "/layer-b"}},
                    "ConmonPidFile": "/run/user/1234/containers/storage/id/conmon.pid",
                    "sandbox_home": "/home/candidate", "candidate_config": "/home/opencode/.config"}
        exported = portable(original, Path("archive"))
        self.assertEqual(exported["StaticDir"], "<host-home>/.local/share/containers/storage/id/userdata")
        self.assertEqual(exported["GraphDriver"]["Data"]["LowerDir"], "<host-home>/layer-a:<host-home>/layer-b")
        self.assertEqual(exported["ConmonPidFile"], "<host-runtime>/containers/storage/id/conmon.pid")
        self.assertEqual(exported["sandbox_home"], original["sandbox_home"])
        self.assertEqual(exported["candidate_config"], original["candidate_config"])
        with self.assertRaisesRegex(ValueError, "private host home"):
            verify_portability(original, "fixture")
        verify_portability(exported, "fixture")


class ExportBoundaryTests(unittest.TestCase):
    def test_export_rejects_nonempty_destination_before_reading_source(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "output"
            output.mkdir()
            existing = output / "stale.txt"
            existing.write_text("retained", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "new or empty"):
                export(Path(folder) / "nonexistent-source", output)
            self.assertEqual(existing.read_text(encoding="utf-8"), "retained")

    def test_verifier_rejects_unlisted_stale_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "export-manifest.json").write_text(json.dumps({"files": [], "generated_files": []}), encoding="utf-8")
            (root / "stale.txt").write_text("unlisted", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Package inventory mismatch.*stale.txt"):
                verify(root)

    def test_corrupted_artifact_is_rejected_with_python_optimization(self):
        source = Path(__file__).resolve().parents[1] / "beam-free-20261017"
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "package"
            shutil.copytree(source, root)
            artifact = root / "trial-02/workspace/racing-kart.FCStd"
            artifact.write_bytes(artifact.read_bytes() + b"corruption-probe")
            result = subprocess.run([sys.executable, "-O", str(Path(__file__).with_name("export_beam.py")),
                                     "--verify", str(root)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("trial-02/workspace/racing-kart.FCStd", result.stderr)


if __name__ == "__main__":
    unittest.main()
