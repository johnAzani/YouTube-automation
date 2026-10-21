"""The OAuth client ID and client secret are stored as separate GitHub secrets."""
import unittest

from pipeline.upload import _client_credentials


class UploadCredentialTests(unittest.TestCase):
    def test_accepts_separate_raw_web_client_values(self):
        self.assertEqual(
            _client_credentials(
                "12345-example.apps.googleusercontent.com",
                "GOCSPX-example-secret",
            ),
            ("12345-example.apps.googleusercontent.com", "GOCSPX-example-secret"),
        )

    def test_trims_whitespace_from_copied_values(self):
        self.assertEqual(
            _client_credentials("  client-id  ", "  raw-secret  "),
            ("client-id", "raw-secret"),
        )

    def test_rejects_missing_either_separate_value(self):
        for client_id, client_secret in (("", "secret"), ("id", "")):
            with self.subTest(client_id=client_id, client_secret=client_secret):
                with self.assertRaisesRegex(RuntimeError, "separate secrets"):
                    _client_credentials(client_id, client_secret)

    def test_rejects_json_in_raw_secret_field_with_clear_guidance(self):
        with self.assertRaisesRegex(RuntimeError, "raw OAuth client secret, not JSON"):
            _client_credentials("client-id", '{"web":{"client_secret":"value"}}')


if __name__ == "__main__":
    unittest.main()
