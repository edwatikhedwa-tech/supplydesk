"""Secret redaction in provider-client error messages.

Covers the owner's explicit requirement that no provider API key ever reach
the browser or a log file verbatim. `requests`' own exception __str__
(HTTPError, ConnectionError, Timeout) embeds the full request URL, so any
provider that authenticates via a URL query parameter can leak its key
through a caught-and-stringified exception unless that message is
redacted first. See TASK-MESSAGES-QUOTE-CHECKO-DESIGN-SEND-20260911 (found
live, in production traffic, via the Checko manual-ИНН lookup) and
ai/DEFERRED_FINDINGS.md FINDING-032 (the follow-up audit that found the
same pattern in the XMLRiver client and confirmed Dellin/RouterAI/DaData
are not exposed, since they authenticate via header or request body,
never a URL query parameter).
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from backend.integrations.secret_redaction import redact_url_credentials
from backend.integrations.registry.checko_client import CheckoClient
from backend.integrations.search.xmlriver_client import XmlRiverClient, XmlRiverError


class RedactUrlCredentialsUnitTests(unittest.TestCase):
    def test_key_param_is_redacted(self) -> None:
        message = "HTTP 401: for url: https://api.checko.ru/v2/company?inn=123&key=REALSECRET"
        result = redact_url_credentials(message)
        self.assertNotIn("REALSECRET", result)
        self.assertIn("key=***", result)
        # Everything else about the URL stays -- this is a diagnostic
        # message, not something to make useless.
        self.assertIn("inn=123", result)
        self.assertIn("HTTP 401", result)

    def test_multiple_credential_param_names_are_redacted(self) -> None:
        for param in ("key", "token", "api_key", "apikey", "appkey", "secret", "access_token"):
            with self.subTest(param=param):
                message = f"error for url https://example.com/x?{param}=REALSECRET&other=1"
                result = redact_url_credentials(message)
                self.assertNotIn("REALSECRET", result)
                self.assertIn("other=1", result)

    def test_message_with_no_credential_param_is_unchanged(self) -> None:
        message = "HTTP 500: for url: https://api.checko.ru/v2/company?inn=123"
        self.assertEqual(redact_url_credentials(message), message)

    def test_case_insensitive_param_name(self) -> None:
        message = "error for url https://example.com/x?Key=REALSECRET"
        result = redact_url_credentials(message)
        self.assertNotIn("REALSECRET", result)


class CheckoClientRedactionTests(unittest.TestCase):
    def test_connection_error_message_never_contains_the_real_key(self) -> None:
        """Reproduces the exact live defect: a caught requests exception's
        __str__ embedding the real key in the URL, previously returned to
        the caller (and from there, the browser) verbatim."""
        client = CheckoClient(key="REALSECRETKEY12345")
        with patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError(
                "HTTPSConnectionPool(host='api.checko.ru', port=443): "
                "Max retries exceeded with url: /v2/company?inn=7707083893&key=REALSECRETKEY12345"
            ),
        ):
            company = client.lookup("7707083893")
        self.assertFalse(company.found)
        self.assertIsNotNone(company.error)
        self.assertNotIn("REALSECRETKEY12345", company.error)
        self.assertIn("key=***", company.error)


class XmlRiverClientRedactionTests(unittest.TestCase):
    def test_connection_error_message_never_contains_the_real_key(self) -> None:
        client = XmlRiverClient(user="1", key="REALSECRETKEY12345", max_retries=1)
        with patch.object(
            client.session,
            "get",
            side_effect=requests.ConnectionError(
                "HTTPSConnectionPool(host='xmlriver.com', port=443): "
                "Max retries exceeded with url: /search/yandex/xml?user=1&key=REALSECRETKEY12345&query=test&page=0"
            ),
        ):
            with self.assertRaises(XmlRiverError) as ctx:
                client.search("test", 0)
        self.assertNotIn("REALSECRETKEY12345", str(ctx.exception))
        self.assertIn("key=***", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
