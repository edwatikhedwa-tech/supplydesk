"""Root compatibility entrypoint for `python collect_contacts.py ...`.

The implementation lives in scripts/collect_contacts.py. Canonical invocation:
    python -m scripts.collect_contacts ...
"""

from __future__ import annotations

import sys

from scripts.collect_contacts import main

if __name__ == "__main__":
    sys.exit(main())
