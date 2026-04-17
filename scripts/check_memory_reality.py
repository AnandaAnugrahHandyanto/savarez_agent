#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from hermes_constants import get_hermes_home


def _line(status: str, name: str, detail: str) -> str:
    return f"{status} {name}: {detail}"


def main() -> int:
    home = get_hermes_home()
    project_root = Path(__file__).resolve().parents[1]
    checks: list[tuple[bool, str]] = []

    checks.append(((home / "memory.db").exists(), _line("PASS" if (home / "memory.db").exists() else "FAIL", "sqlite-memory-db", str(home / "memory.db"))))

    for mod_name, label in (
        ("agent.memory_event", "control-plane-memory-event"),
        ("agent.recall_receipt", "control-plane-recall-receipt"),
        ("agent.write_compiler", "control-plane-write-compiler"),
        ("agent.recall_assembler", "control-plane-recall-assembler"),
    ):
        try:
            __import__(mod_name)
            checks.append((True, _line("PASS", label, f"{mod_name} importable")))
        except Exception as exc:
            checks.append((False, _line("FAIL", label, str(exc))))

    compact_ok = hasattr(__import__("tools.session_search_tool", fromlist=["session_search_compact"]), "session_search_compact")
    checks.append((compact_ok, _line("PASS" if compact_ok else "FAIL", "compact-session-recall-bridge", "session_search_compact callable" if compact_ok else "missing session_search_compact")))

    for path, label in (
        (home / "state" / "last_memory_event.json", "memory-event-receipt"),
        (home / "state" / "last_recall_receipt.json", "recall-receipt"),
    ):
        exists = path.exists()
        checks.append((exists, _line("PASS" if exists else "WARN", label, str(path) if exists else f"{path} not created yet")))

    failed = False
    for ok, line in checks:
        print(line)
        if line.startswith("FAIL"):
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
