#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from hermes_constants import get_hermes_home


def main() -> int:
    path = get_hermes_home() / "state" / "last_recall_receipt.json"
    if not path.exists():
        print(json.dumps({"ok": False, "error": f"missing {path}"}, ensure_ascii=False))
        return 1
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = {
        "ok": True,
        "query_type": payload.get("query_type"),
        "lanes_used": payload.get("lanes_used", []),
        "degraded_flags": payload.get("degraded_flags", []),
        "winning_record_count": len(payload.get("winning_records") or []),
        "context_block_length": len(payload.get("context_block") or ""),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
