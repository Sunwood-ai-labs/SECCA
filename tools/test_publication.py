"""Publication guard behavior using generated, non-secret fixture values."""

import unittest

from check_publication import scan_payload


class PublicationTests(unittest.TestCase):
    def test_candidate_value_is_never_reported(self):
        candidate = b'gh' + b'p_' + b'fixture' * 8
        failures = scan_payload('README.md', candidate)
        self.assertEqual(len(failures), 1)
        self.assertIn('github_token', failures[0])
        self.assertNotIn(candidate.decode(), failures[0])

    def test_known_negative_url_fixture_is_narrowly_allowed(self):
        fixture = b'https' + b'://user' + b':pass@example.org/v1'
        self.assertEqual(scan_payload('scripts/test_gateway.py', fixture), [])
        self.assertTrue(scan_payload('README.md', fixture))
        other = b'https' + b'://someone' + b':different@example.org/v1'
        self.assertTrue(scan_payload('scripts/test_gateway.py', other))

    def test_fixture_file_does_not_exempt_other_credentials(self):
        candidate = b'sk' + b'-' + b'fixture' * 8
        self.assertTrue(scan_payload('scripts/test_gateway.py', candidate))

    def test_host_metadata_is_rejected_outside_frozen_assets(self):
        host_path = b'C:' + bytes([92]) + b'Users' + bytes([92]) + b'fixture' + bytes([92]) + b'log'
        self.assertTrue(scan_payload('references/verification/result.json', host_path))
        self.assertEqual(scan_payload('assets/baseline/evidence/run.json', host_path), [])
        self.assertTrue(scan_payload('experiments/run.json', b'embedding' + b'gemma2-lab'))

    def test_sandbox_paths_are_not_private_host_metadata(self):
        self.assertEqual(scan_payload('container/runtime.py', b'/home/candidate/.cache/runtime'), [])
        self.assertTrue(scan_payload('experiments/run.json', b'/home/' + b'fixture/.local/storage'))


if __name__ == '__main__':
    unittest.main()
