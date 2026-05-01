#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Inspect current IFIND configuration state without making external requests.

Usage:
  python scripts/inspect_ifind_config.py
  IFIND_REFRESH_TOKEN=... IFIND_BASE_URL=https://... python scripts/inspect_ifind_config.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

HOOKS_DIR = Path.home() / ".claude" / "hooks"
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))
try:
    from runtime_utils import load_runtime_env  # type: ignore
except Exception:
    load_runtime_env = None
if load_runtime_env:
    load_runtime_env()

from ifind_client import IFINDClient


def main() -> None:
    client = IFINDClient()
    print(json.dumps(client.probe(), ensure_ascii=False, indent=2))
    print(json.dumps(client.get_access_token(), ensure_ascii=False, indent=2))
    print(json.dumps(client.refresh_access_token(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
