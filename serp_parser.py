"""Root compatibility entrypoint for `python serp_parser.py ...`.

The implementation lives in backend/integrations/search/serp_parser.py.
Canonical invocation:
    python -m backend.integrations.search.serp_parser ...
"""

from __future__ import annotations

import sys

from backend.integrations.search.serp_parser import main

if __name__ == "__main__":
    sys.exit(main())
