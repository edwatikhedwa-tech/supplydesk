"""Vercel adapter for the existing Supplydesk HTTP handler.

The application remains the source of truth. This module only supplies the
BaseHTTPRequestHandler entry point expected by Vercel's Python runtime and
serves the existing HTML/static assets through the same handler.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from supplier_app import (  # noqa: E402
    Config,
    SupplierApp,
    SupplierHandler,
    load_dotenv,
)


# Local `vercel dev` can use the existing .env. The deployed function receives
# values from Vercel Environment Variables; the file is excluded from deploys.
load_dotenv(PROJECT_ROOT / ".env")

# Vercel Functions have an ephemeral writable /tmp. This fallback keeps local
# and misconfigured previews runnable; production must provide DATABASE_URL for
# shared durable storage.
os.environ.setdefault("MAIL_DB_PATH", "/tmp/supplydesk.sqlite3")

# Preview deployments get a usable callback fallback. Production should set
# APP_BASE_URL and YANDEX_REDIRECT_URI explicitly to the stable public URL.
if not os.getenv("APP_BASE_URL") and os.getenv("VERCEL_URL"):
    os.environ["APP_BASE_URL"] = f"https://{os.environ['VERCEL_URL']}"
if not os.getenv("YANDEX_REDIRECT_URI") and os.getenv("APP_BASE_URL"):
    os.environ["YANDEX_REDIRECT_URI"] = f"{os.environ['APP_BASE_URL'].rstrip('/')}/oauth/yandex/callback"


_APP = SupplierApp(Config.from_env())
# Keep the existing bounded queue behavior for warm function instances. Vercel
# may recycle instances at any time, so durable sending requires an external
# queue/worker in a later production hardening step.
_APP.queue.start()


class handler(SupplierHandler):
    @property
    def app(self) -> SupplierApp:
        return _APP
