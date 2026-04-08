"""Shared developer-environment preflight checks."""

from __future__ import annotations

import importlib.util
from typing import Callable


REQUIRED_TEST_MODULES = {
    "prompt_toolkit": "required by CLI command/help imports used in tests",
    "pytest_asyncio": "required for @pytest.mark.asyncio gateway tests",
    "xdist": "required because pytest defaults to '-n auto' in pyproject.toml",
}


def find_missing_test_modules(
    find_spec: Callable[[str], object | None] = importlib.util.find_spec,
) -> dict[str, str]:
    """Return missing test-environment modules mapped to the reason they matter."""
    missing: dict[str, str] = {}
    for module_name, reason in REQUIRED_TEST_MODULES.items():
        if find_spec(module_name) is None:
            missing[module_name] = reason
    return missing


def test_install_command() -> str:
    """Return the preferred command for installing the Hermes dev environment."""
    return 'uv pip install -e ".[all,dev]"'


def test_install_hint() -> str:
    """Return multi-line install guidance for missing test dependencies."""
    return (
        "Install the dev environment with:\n"
        f"  {test_install_command()}\n"
        "or:\n"
        '  pip install -e ".[all,dev]"'
    )
