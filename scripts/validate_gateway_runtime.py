#!/usr/bin/env python3
"""Validate persisted Hermes gateway runtime artifacts.

Prints a compact summary and exits non-zero when any persisted runtime artifact is
present but invalid.
"""

from __future__ import annotations

import json
import sys

from gateway.status import validate_runtime_artifacts


def main() -> int:
    report = validate_runtime_artifacts()
    print(json.dumps(report, indent=2, sort_keys=True))

    invalid_sections = []
    for name in ("pid", "runtime_status"):
        section = report.get(name, {})
        if section.get("exists") and not section.get("valid"):
            invalid_sections.append(name)

    return 1 if invalid_sections else 0


if __name__ == "__main__":
    raise SystemExit(main())
