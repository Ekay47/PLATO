import unittest

from src.core.errors import to_error_payload


class ErrorPayloadTests(unittest.TestCase):
    def test_config_error_mapping(self):
        payload = to_error_payload(Exception("invalid config setting"))
        self.assertEqual(payload["error_code"], "CONFIG_INVALID")
        self.assertEqual(payload["error_type"], "config")

    def test_dependency_error_mapping(self):
        payload = to_error_payload(Exception("CoreNLP dependency parse request failed: timeout"))
        self.assertEqual(payload["error_code"], "DEPENDENCY_UNAVAILABLE")
        self.assertEqual(payload["error_type"], "dependency")

    def test_output_error_mapping(self):
        payload = to_error_payload(Exception("json parse failed"))
        self.assertEqual(payload["error_code"], "OUTPUT_INVALID")
        self.assertEqual(payload["error_type"], "output")

    def test_default_error_mapping(self):
        payload = to_error_payload(Exception("unknown failure"))
        self.assertEqual(payload["error_code"], "PIPELINE_FAILED")
        self.assertEqual(payload["error_type"], "pipeline")
        self.assertIn("detail", payload)


if __name__ == "__main__":
    unittest.main()
