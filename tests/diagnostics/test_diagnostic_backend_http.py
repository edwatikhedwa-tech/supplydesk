import unittest
from unittest.mock import patch

from scripts.diagnostics.diagnostic_runner import backend_http_check


class DiagnosticBackendHttpTests(unittest.TestCase):
    def test_expected_200_401_404_contract_passes(self):
        expected = {"/": 200, "/api/auth/me": 200, "/api/mail/status": 401, "/api/diagnostic-unknown": 404}

        def fake_status(url):
            for path, status in expected.items():
                if url.endswith(path):
                    return status, "mock"
            return None, "mock"

        with patch("scripts.diagnostics.diagnostic_runner.http_status", side_effect=fake_status):
            result = backend_http_check("http://test")
        self.assertEqual(result.status, "PASS")

    def test_unexpected_status_is_product_failure(self):
        with patch("scripts.diagnostics.diagnostic_runner.http_status", return_value=(500, "mock")):
            result = backend_http_check("http://test")
        self.assertEqual(result.status, "PRODUCT_FAILURE")
        self.assertEqual(result.diagnostic_code, "BACKEND_HTTP_FAIL")


if __name__ == "__main__":
    unittest.main()
