#!/usr/bin/env python3
"""CLI: OpenClaw LINE/Telegram channel readiness report (Hermes-native port)."""

from __future__ import annotations

import argparse
import json
import sys

from tools.openclaw.channel_readiness import build_channel_readiness
from tools.openclaw.paths import default_openclaw_config_path, default_openclaw_state_root


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw channel readiness diagnostics.")
    parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Path to openclaw.json (default: OPENCLAW_CONFIG or ~/.openclaw/openclaw.json)",
    )
    args = parser.parse_args()
    cfg = default_openclaw_config_path() if not args.config else __import__("pathlib").Path(args.config).expanduser()
    state = cfg.parent if cfg.is_file() else default_openclaw_state_root()
    report = build_channel_readiness(cfg, state)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
