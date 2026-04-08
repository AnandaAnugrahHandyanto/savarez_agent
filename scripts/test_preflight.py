#!/usr/bin/env python3
"""Check that the local environment can run the Hermes test suite."""

from __future__ import annotations

import sys
from hermes_cli.dev_preflight import find_missing_test_modules, test_install_hint


def find_missing_modules(find_spec=None) -> dict[str, str]:
    """Backward-compatible wrapper for tests and scripts."""
    return find_missing_test_modules(find_spec=find_spec)


def install_hint() -> str:
    """Backward-compatible wrapper for tests and scripts."""
    return test_install_hint()


def main() -> int:
    missing = find_missing_modules()
    if not missing:
        print("Hermes test preflight passed.")
        print("You can run: pytest tests/ -q")
        return 0

    print("Hermes test preflight failed.")
    print("Missing Python packages:")
    for module_name, reason in missing.items():
        print(f"  - {module_name}: {reason}")
    print()
    print(install_hint())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
