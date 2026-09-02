"""Root compatibility entrypoint for `python benchmark_models.py ...`.

The implementation lives in benchmarks/benchmark_models.py. Canonical invocation:
    python -m benchmarks.benchmark_models ...
"""

from __future__ import annotations

import sys

from benchmarks.benchmark_models import main

if __name__ == "__main__":
    sys.exit(main())
