"""Real CLI subprocess checks with a Windows single-byte output encoding."""

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent


class CliEncodingTests(unittest.TestCase):
    def invoke(self, arguments):
        environment = dict(os.environ, PYTHONIOENCODING="cp1252:strict", PYTHONUTF8="0")
        result = subprocess.run([sys.executable, *arguments], cwd=ROOT, env=environment,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode("ascii", errors="backslashreplace"))
        self.assertTrue(result.stdout.isascii())
        return json.loads(result.stdout.decode("ascii"))

    def test_real_baseline_cli_outputs_valid_json_with_cp1252_stdout(self):
        result = self.invoke([str(ROOT / "scripts/scores.py"), "verify-baseline"])
        self.assertEqual(result["score"], 43)
        self.assertEqual(result["historical_review_totals"], [45, 42, 42])

    def test_candidate_cli_preserves_unicode_result_with_cp1252_stdout(self):
        code = (
            "import sys; sys.path.insert(0, 'scripts'); import candidate; "
            "candidate.verify_assets = lambda: {'status': 'verified', 'label': '\\u96ea\\u83ef'}; "
            "sys.argv = ['candidate.py', 'verify-assets']; raise SystemExit(candidate.main())"
        )
        result = self.invoke(["-c", code])
        self.assertEqual(result, {"status": "verified", "label": "\u96ea\u83ef"})


if __name__ == "__main__":
    unittest.main()
