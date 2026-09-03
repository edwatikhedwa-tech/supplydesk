"""
Static-asset and SPA-shell helpers, extracted from supplier_app.py
(TASK-BOUNDED-SUPPLIER-APP-CONFIG-EXTRACT-20260903) as part of turning
supplier_app.py into a thin composition entrypoint. No behavior changed:
every function/constant below is moved byte-for-byte from supplier_app.py,
only the ROOT computation is adjusted to this file's own location.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The built React SPA (frontend/npm run build). Its assets are hashed and public;
# nothing under ROOT besides this directory and the font files below is servable.
FRONTEND_DIST = ROOT / "frontend" / "dist"

# Extensions that only ever belong to server-side source or config. A React
# Router path never ends in one of these, so such a request is either a probe
# or a typo — both deserve a plain 404 rather than the SPA shell.
_SOURCE_SUFFIXES = (
    ".py", ".pyc", ".sql", ".env", ".ini", ".cfg", ".toml", ".yaml", ".yml",
    ".sqlite3", ".db", ".log", ".sh", ".ps1", ".bak", ".pem", ".key",
)


def _looks_like_source_path(path: str) -> bool:
    tail = path.rsplit("/", 1)[-1].lower()
    return tail.startswith(".env") or tail.endswith(_SOURCE_SUFFIXES)


def load_fixture_data() -> dict:
    """Read the demo supplier catalog once so a fresh workspace has seed data."""
    return json.loads((ROOT / "fixtures" / "demo_catalog.json").read_text(encoding="utf-8"))
