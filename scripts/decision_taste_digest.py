#!/usr/bin/env python3
"""Compile Telegram DecisionCard outcomes into a taste-memory digest.

This script is intentionally lightweight and local-first:
- reads $HERMES_HOME/decision_queue/decisions.jsonl
- tracks processed ledger records in $HERMES_HOME/decision_queue/taste_digest_state.json
- writes a canonical markdown digest in Dropbox brain-sync
- optionally writes a compact Cortex memory via `cmem remember`

It prints only when new records were processed, so it can be used as a quiet
no-agent cron script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_WIKI_PATH = Path(
    "/Users/joohyunkim/Library/CloudStorage/Dropbox/brain-sync/projects/mina-operating-system/decision-taste-digest.md"
)


@dataclass(frozen=True)
class DecisionRecord:
    key: str
    raw: dict[str, Any]

    @property
    def decision_id(self) -> str:
        return str(self.raw.get("decision_id") or "")

    @property
    def choice(self) -> str:
        return str(self.raw.get("choice") or "")

    @property
    def selected_label(self) -> str:
        return str(self.raw.get("selected_label") or "")

    @property
    def free_text_reason(self) -> str:
        return str(self.raw.get("free_text_reason") or "")

    @property
    def title(self) -> str:
        return str(self.raw.get("title") or "")

    @property
    def recommendation(self) -> str:
        return str(self.raw.get("recommendation") or "")

    @property
    def taste_signal(self) -> str:
        return str(self.raw.get("taste_signal") or "")

    @property
    def recorded_at(self) -> str:
        return str(self.raw.get("recorded_at") or "")


def _hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes").expanduser()


def _record_key(raw: dict[str, Any], line_no: int) -> str:
    parts = [
        str(raw.get("decision_id") or ""),
        str(raw.get("recorded_at") or ""),
        str(raw.get("choice") or ""),
        str(raw.get("user_id") or ""),
        str(line_no),
    ]
    return "|".join(parts)


def load_decisions(path: Path) -> list[DecisionRecord]:
    if not path.exists():
        return []
    records: list[DecisionRecord] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(raw, dict):
                records.append(DecisionRecord(_record_key(raw, line_no), raw))
    return records


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"processed_keys": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("processed_keys", [])
            return data
    except Exception:
        pass
    return {"processed_keys": []}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _human_choice(record: DecisionRecord) -> str:
    if record.choice == "__other__":
        return f"직접 입력: {record.free_text_reason}" if record.free_text_reason else "직접 입력"
    if record.choice == "__defer__":
        return "Defer"
    if record.choice == "__cancel__":
        return "Cancel"
    return record.selected_label or record.choice


def _infer_signals(records: Iterable[DecisionRecord]) -> list[str]:
    records = list(records)
    signals: list[str] = []
    total = len(records)
    direct = [r for r in records if r.choice == "__other__"]
    deferred = [r for r in records if r.choice == "__defer__" or (r.selected_label or "").lower() == "defer"]
    cancelled = [r for r in records if r.choice == "__cancel__"]
    recs = [r for r in records if r.recommendation]
    followed = [r for r in recs if r.choice == r.recommendation]

    if total:
        signals.append(f"Processed {total} new DecisionCard outcome(s).")
    if recs:
        signals.append(f"Recommendation follow-rate: {len(followed)}/{len(recs)}.")
    if direct:
        signals.append(
            f"Direct-input corrections appeared {len(direct)} time(s); treat these as high-value taste labels, not noise."
        )
    if deferred:
        signals.append(f"Deferral appeared {len(deferred)} time(s); check whether Mina asked too early or with insufficient context.")
    if cancelled:
        signals.append(f"Cancellation appeared {len(cancelled)} time(s); reduce interruption or improve framing for similar cards.")

    by_signal = Counter((r.taste_signal or r.title or "unspecified") for r in records)
    for signal, count in by_signal.most_common(5):
        signals.append(f"Repeated taste axis ({count}): {signal}")
    return signals


def build_digest(records: list[DecisionRecord]) -> dict[str, Any]:
    by_signal: dict[str, list[DecisionRecord]] = defaultdict(list)
    for r in records:
        by_signal[r.taste_signal or r.title or "unspecified"].append(r)

    clusters = []
    for signal, items in sorted(by_signal.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        choices = Counter(_human_choice(r) for r in items)
        examples = []
        for r in items[:5]:
            examples.append(
                {
                    "decision_id": r.decision_id,
                    "title": r.title,
                    "choice": r.choice,
                    "selected": _human_choice(r),
                    "recommendation": r.recommendation,
                    "free_text_reason": r.free_text_reason,
                    "recorded_at": r.recorded_at,
                }
            )
        clusters.append(
            {
                "taste_signal": signal,
                "count": len(items),
                "choice_counts": dict(choices),
                "examples": examples,
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "new_records": len(records),
        "signals": _infer_signals(records),
        "clusters": clusters,
    }


def render_markdown(digest: dict[str, Any], existing: str = "") -> str:
    generated_at = digest["generated_at"]
    latest_lines = [
        "# Joohyun Decision Taste Digest",
        "",
        "This page is the canonical human-readable digest for Mina/Hermes DecisionCard taste signals.",
        "Raw outcomes live in `~/.hermes/decision_queue/decisions.jsonl`; this page keeps the compact operating interpretation.",
        "",
        f"_Last updated: {generated_at}_",
        "",
        "## Current operating read",
    ]
    for sig in digest.get("signals", []):
        latest_lines.append(f"- {sig}")
    if not digest.get("signals"):
        latest_lines.append("- No new taste signals processed yet.")

    latest_lines.extend(["", "## Taste clusters"])
    for cluster in digest.get("clusters", []):
        latest_lines.extend([
            "",
            f"### {cluster['taste_signal']}",
            f"- New outcomes: {cluster['count']}",
            "- Choice distribution:",
        ])
        for choice, count in cluster.get("choice_counts", {}).items():
            latest_lines.append(f"  - {choice}: {count}")
        latest_lines.append("- Representative records:")
        for ex in cluster.get("examples", []):
            selected = ex.get("selected") or ex.get("choice")
            rec = ex.get("recommendation") or "none"
            latest_lines.append(f"  - `{ex.get('decision_id')}` — {ex.get('title')}: selected `{selected}`; Mina rec `{rec}`")
            if ex.get("free_text_reason"):
                latest_lines.append(f"    - direct input: {ex['free_text_reason']}")

    history_entry = [
        "",
        "## Run history",
        "",
        f"### {generated_at}",
        f"- New records: {digest['new_records']}",
    ]
    for sig in digest.get("signals", []):
        history_entry.append(f"- {sig}")

    if "## Run history" in existing:
        _, old_history = existing.split("## Run history", 1)
        return "\n".join(latest_lines) + "\n" + "\n".join(history_entry[1:]) + old_history
    return "\n".join(latest_lines + history_entry) + "\n"


def compact_cmem_content(digest: dict[str, Any], wiki_path: Path) -> str:
    lines = [
        f"Processed {digest['new_records']} new Mina/Hermes DecisionCard outcome(s).",
        f"Wiki digest: {wiki_path}",
    ]
    lines.extend(digest.get("signals", [])[:8])
    for cluster in digest.get("clusters", [])[:5]:
        lines.append(f"Taste axis: {cluster['taste_signal']} | choices={cluster['choice_counts']}")
    return "\n".join(lines)


def write_cmem(digest: dict[str, Any], wiki_path: Path, *, dry_run: bool = False) -> tuple[bool, str]:
    title = f"Mina DecisionCard taste digest {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    content = compact_cmem_content(digest, wiki_path)
    if dry_run:
        return True, "dry-run: skipped cmem write"
    cmd = [
        "cmem",
        "remember",
        "--type",
        "context",
        "--title",
        title,
        "--content",
        content,
        "--project",
        "hermes",
    ]
    env = os.environ.copy()
    env.setdefault("CMEM_LOCAL_ONLY", "1")
    try:
        proc = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=20)
    except Exception as exc:
        return False, f"cmem write failed: {exc}"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout or f"cmem exited {proc.returncode}").strip()
    return True, (proc.stdout or "cmem write ok").strip()


def run(
    *,
    ledger_path: Path,
    state_path: Path,
    wiki_path: Path,
    dry_run: bool = False,
    no_cmem: bool = False,
    force: bool = False,
) -> str:
    all_records = load_decisions(ledger_path)
    state = load_state(state_path)
    processed = set(str(k) for k in state.get("processed_keys", []))
    new_records = all_records if force else [r for r in all_records if r.key not in processed]
    if not new_records:
        return ""

    digest = build_digest(new_records)
    existing = wiki_path.read_text(encoding="utf-8") if wiki_path.exists() else ""
    rendered = render_markdown(digest, existing)

    if not dry_run:
        wiki_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = wiki_path.with_suffix(".tmp")
        tmp.write_text(rendered, encoding="utf-8")
        tmp.replace(wiki_path)

        runs_path = state_path.parent / "taste_digest_runs.jsonl"
        with runs_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(digest, ensure_ascii=False) + "\n")

        state["processed_keys"] = sorted(processed | {r.key for r in new_records})
        state["last_run_at"] = digest["generated_at"]
        state["last_wiki_path"] = str(wiki_path)
        save_state(state_path, state)

    cmem_ok, cmem_msg = (True, "cmem disabled") if no_cmem else write_cmem(digest, wiki_path, dry_run=dry_run)

    status = "ok" if cmem_ok else "partial"
    lines = [
        f"Decision taste digest {status}: processed {len(new_records)} new record(s).",
        f"Wiki: {wiki_path}",
        f"Cortex: {cmem_msg}",
    ]
    lines.extend(f"- {s}" for s in digest.get("signals", [])[:6])
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    home = _hermes_home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=home / "decision_queue" / "decisions.jsonl")
    parser.add_argument("--state", type=Path, default=home / "decision_queue" / "taste_digest_state.json")
    parser.add_argument("--wiki", type=Path, default=DEFAULT_WIKI_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-cmem", action="store_true")
    parser.add_argument("--force", action="store_true", help="Process all records regardless of state")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    output = run(
        ledger_path=args.ledger.expanduser(),
        state_path=args.state.expanduser(),
        wiki_path=args.wiki.expanduser(),
        dry_run=args.dry_run,
        no_cmem=args.no_cmem,
        force=args.force,
    )
    if output:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
