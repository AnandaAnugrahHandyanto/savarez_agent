#!/usr/bin/env python3
"""Cron wrapper for `hermes model --refresh` cache maintenance."""

from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HERMES_HOME = Path(
    os.environ.get("HERMES_HOME") or Path.home() / ".hermes"
).expanduser().resolve()

os.environ.setdefault("HERMES_HOME", str(HERMES_HOME))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hermes_cli.model_refresh import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(json_output=True, wake_gate=True, exit_failure=False))
