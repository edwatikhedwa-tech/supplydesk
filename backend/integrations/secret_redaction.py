"""Shared secret-redaction helper for provider-client error messages.

`requests`'s own exceptions (`HTTPError`, `ConnectionError`, `Timeout`, ...)
embed the full request URL in their default `str()` -- for any provider
client that authenticates via a URL query parameter (Checko, XMLRiver: both
`?key=...`), that means a caught exception's message can silently carry the
real credential. A message built with `f"...{exc}"` looks harmless at the
call site; the leak only shows up once that message reaches a browser
network response or a log file someone else can read.

Originally found and fixed in `backend/integrations/registry/checko_client.py`
(the Checko API key was reaching the browser verbatim in a `/inn` lookup's
error response). This module exists so the same fix does not need
rediscovering per client -- every provider client that builds an error
message from a caught `requests` exception should route it through
`redact_url_credentials` first. See ai/DEFERRED_FINDINGS.md FINDING-032.
"""

from __future__ import annotations

import re

_CREDENTIAL_PARAM_RE = re.compile(
    r"([?&](?:key|token|api[_-]?key|appkey|secret|access[_-]?token)=)[^&\s]+",
    re.IGNORECASE,
)


def redact_url_credentials(message: str) -> str:
    """Scrub common credential-bearing query params (key=, token=, appkey=,
    api_key=, secret=, access_token=) from a message that may embed a full
    request URL."""
    return _CREDENTIAL_PARAM_RE.sub(r"\1***", message)
