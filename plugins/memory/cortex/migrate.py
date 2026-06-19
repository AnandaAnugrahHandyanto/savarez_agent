"""Migrate Hermes built-in memory files into the Cortext graph.

Reads $HERMES_HOME/memories/MEMORY.md (entries separated by `§`) and
USER.md (paragraphs), stores each chunk as a W5H memory in the Cortex
graph, and persists to $HERMES_HOME/cortext_<namespace>.json — the same
file the cortex provider loads at startup.

Idempotent-ish: skips chunks whose `what` already exists in the graph.

Usage:
    HERMES_HOME=~/.hermes python plugins/memory/cortex/migrate.py
    # options:
    #   --namespace hermes   (default: hermes)
    #   --dry-run            (parse + report, write nothing)
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def _split_chunks(text: str) -> list[str]:
    """Split on `§` separators; fall back to blank-line paragraphs."""
    text = (text or "").strip()
    if not text:
        return []
    if "§" in text:
        parts = [p.strip() for p in text.split("§")]
    else:
        parts = [p.strip() for p in re.split(r"\n\s*\n", text)]
    return [p for p in parts if p]


def _candidate_who(chunk: str) -> list[str]:
    """Extract capitalized project/proper names as participants (heuristic)."""
    # ALL-CAPS tokens (project codenames) + Capitalized multiword phrases
    caps = re.findall(r"\b[A-ZÀ-Ý][A-ZÀ-Ý0-9\-]{2,}\b", chunk)
    seen: list[str] = []
    for c in caps:
        if c not in seen and c not in {"CLI", "SDK", "MCP", "PDF", "SM", "BFS"}:
            seen.append(c)
    return seen[:4]


def migrate(namespace: str = "hermes", dry_run: bool = False) -> dict:
    from cortext.integration.hermes_bridge import HermesCortexBridge
    from cortext.core.graph import MemoryGraph

    home = _hermes_home()
    mem_dir = home / "memories"
    store_path = home / f"cortext_{namespace}.json"

    sources = {
        "MEMORY.md": ("project", "hermes-memory"),
        "USER.md": ("user", "hermes-user"),
    }

    bridge = HermesCortexBridge(namespace=namespace)
    # Load existing graph so we append rather than clobber.
    if store_path.exists():
        bridge.cortex.graph = MemoryGraph.load(store_path, namespace=namespace)

    existing_what = {m.what for m in bridge.cortex.graph.iter_memories()}

    report = {"files": {}, "added": 0, "skipped": 0, "store": str(store_path)}

    for fname, (kind, where) in sources.items():
        path = mem_dir / fname
        if not path.exists():
            report["files"][fname] = "missing"
            continue
        chunks = _split_chunks(path.read_text(encoding="utf-8"))
        added = skipped = 0
        for chunk in chunks:
            if chunk in existing_what:
                skipped += 1
                continue
            if not dry_run:
                bridge.cortex.remember(
                    who=_candidate_who(chunk),
                    what=chunk,
                    where=where,
                    importance=0.85,          # curated profile facts = high value
                    lang="pt",
                    validate=False,            # trust curated source, no contradiction gate
                )
            existing_what.add(chunk)
            added += 1
        report["files"][fname] = {"chunks": len(chunks), "added": added, "skipped": skipped}
        report["added"] += added
        report["skipped"] += skipped

    if not dry_run and report["added"]:
        bridge.cortex.graph.save(store_path)

    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="Migrate Hermes memories into Cortext")
    ap.add_argument("--namespace", default="hermes")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    report = migrate(namespace=args.namespace, dry_run=args.dry_run)

    print(f"{'[DRY RUN] ' if args.dry_run else ''}Migration → {report['store']}")
    for fname, info in report["files"].items():
        print(f"  {fname}: {info}")
    print(f"  TOTAL added={report['added']} skipped={report['skipped']}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    main()
