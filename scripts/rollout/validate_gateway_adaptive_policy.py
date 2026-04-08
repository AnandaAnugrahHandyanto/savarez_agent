#!/usr/bin/env python3
"""Validate gateway adaptive policy and telemetry artifacts.

Usage:
  python scripts/rollout/validate_gateway_adaptive_policy.py [~/.hermes]
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def main() -> int:
    home = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path.home() / ".hermes"
    policy_path = home / "gateway_adaptive_policy.json"
    telemetry_path = home / "gateway_telemetry.jsonl"
    signatures_path = home / "gateway_failure_signatures.json"

    print(f"Hermes home: {home}")

    if policy_path.exists():
        try:
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            print("policy: OK")
            print(json.dumps(policy.get("policy", {}), indent=2))
            scope = policy.get("auto_remediation_scope", {}) if isinstance(policy, dict) else {}
            if scope:
                print("auto_remediation_scope:")
                print(json.dumps(scope, indent=2))
        except Exception as e:
            print(f"policy: ERROR ({e})")
            return 1
    else:
        print("policy: missing (adaptive evaluator may not have run yet)")

    if telemetry_path.exists():
        rows = _load_jsonl(telemetry_path)
        print(f"telemetry: {len(rows)} event(s)")
        kinds = Counter(str(r.get("kind", "unknown")) for r in rows)
        if kinds:
            print("telemetry kinds:")
            for kind, count in sorted(kinds.items()):
                print(f"  - {kind}: {count}")

        # Basic schema presence checks (warn-only):
        required_agent_turn = ["duration_s", "api_calls", "failed", "response_chars", "tool_failures"]
        sample_turn = next((r for r in rows if r.get("kind") == "agent_turn"), None)
        if sample_turn:
            missing = [k for k in required_agent_turn if k not in sample_turn]
            if missing:
                print(f"telemetry: WARN agent_turn missing keys: {missing}")
            else:
                print("telemetry: agent_turn schema OK")

        has_user_signals = any(r.get("kind") == "user_signal" for r in rows)
        has_context_compression = any(r.get("kind") == "context_compression" for r in rows)
        has_reconnect = any(r.get("kind") == "reconnect_result" for r in rows)
        print(
            "telemetry signals: "
            f"user_signal={'yes' if has_user_signals else 'no'}, "
            f"context_compression={'yes' if has_context_compression else 'no'}, "
            f"reconnect_result={'yes' if has_reconnect else 'no'}"
        )
    else:
        print("telemetry: missing")

    if signatures_path.exists():
        try:
            signatures = json.loads(signatures_path.read_text(encoding="utf-8"))
            print(f"signatures: {len(signatures)} signature(s)")
        except Exception as e:
            print(f"signatures: ERROR ({e})")
            return 1
    else:
        print("signatures: missing")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
