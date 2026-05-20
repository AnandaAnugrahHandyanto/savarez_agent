"""Test bootstrap for the thin Hermes ContextOps adapter skeleton.

Makes both the adapter package and the standalone ``contextops_ese`` core
importable without an install step.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_CORE_SRC = _REPO_ROOT / "packages" / "contextops_ese" / "src"
for _p in (str(_REPO_ROOT), str(_CORE_SRC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
