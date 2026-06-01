"""Single truthful probe for the optional Pipecat dependency.

Pipecat ships in the opt-in ``simplex-streaming`` extra. These helpers let
callers (the engine deferral, the smoke test, and later slices) check
availability without scattering try/import blocks. Neither helper raises.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _pkg_version

# Distribution name on PyPI (import name is ``pipecat``).
_DISTRIBUTION = "pipecat-ai"


def _distribution_version(name: str) -> str | None:
    try:
        return _pkg_version(name)
    except PackageNotFoundError:
        return None


def pipecat_available() -> bool:
    """True iff ``import pipecat`` succeeds. Import is inside the function so
    tests can simulate absence by patching ``builtins.__import__``."""
    try:
        import pipecat  # noqa: F401
    except Exception:
        return False
    return True


def pipecat_version() -> str | None:
    """Installed Pipecat version, or None when absent. Never raises."""
    return _distribution_version(_DISTRIBUTION)
