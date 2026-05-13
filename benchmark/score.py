#!/usr/bin/env python3
"""
benchmark/score.py — Interactive scoring + win-rate analysis.

Usage:
    python benchmark/score.py           # label all unscored pairs interactively
    python benchmark/score.py --report  # print report only (no interactive prompts)

Input:  benchmark/results/deepparser.jsonl + benchmark/results/llamaindex.jsonl
Output: benchmark/results/scored.json + benchmark/results/report.md
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

BENCH_DIR = Path(__file__).parent
RESULTS_DIR = BENCH_DIR / "results"
QA_PAIRS_FILE = BENCH_DIR / "qa_pairs.json"

DEEPPARSER_FILE = RESULTS_DIR / "deepparser.jsonl"
LLAMAINDEX_FILE = RESULTS_DIR / "llamaindex.jsonl"
SCORED_FILE = RESULTS_DIR / "scored.json"
REPORT_FILE = RESULTS_DIR / "report.md"


def _load_jsonl(path: Path) -> dict[str, dict]:
    """Return {question_id: record} from a .jsonl file."""
    out: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
                out[r["question_id"]] = r
            except Exception:
                pass
    return out


def _load_scores() -> dict[str, dict]:
    if SCORED_FILE.exists():
        return json.loads(SCORED_FILE.read_text())
    return {}


def _save_scores(scores: dict[str, dict]) -> None:
    SCORED_FILE.write_text(json.dumps(scores, indent=2, ensure_ascii=False))


def _truncate(text: str | None, n: int = 300) -> str:
    if not text:
        return "(no answer)"
    return text[:n] + "..." if len(text) > n else text


# ---------------------------------------------------------------------------
# Interactive labeling
# ---------------------------------------------------------------------------

def label_pairs(qa_pairs: dict, dp: dict, li: dict, scores: dict) -> dict:
    all_questions = [
        (doc["id"], doc["category"], q)
        for doc in qa_pairs["docs"]
        for q in doc["questions"]
    ]
    unlabeled = [
        (did, cat, q) for (did, cat, q) in all_questions
        if q["id"] not in scores
    ]

    if not unlabeled:
        print("All pairs already scored.")
        return scores

    print(f"\nScoring {len(unlabeled)} unlabeled pairs (Ctrl+C to stop and save progress).\n")
    print("For each pair enter:")
    print("  d  = DeepParser wins (correct / more complete)")
    print("  l  = LlamaIndex wins")
    print("  t  = Tie (both correct or both wrong)")
    print("  s  = Skip (come back later)")
    print("  q  = Quit and save\n")

    try:
        for idx, (doc_id, category, q) in enumerate(unlabeled, 1):
            qid = q["id"]
            dp_rec = dp.get(qid, {})
            li_rec = li.get(qid, {})

            print(f"\n{'─'*60}")
            print(f"[{idx}/{len(unlabeled)}] {qid}  ({category})")
            print(f"Question: {q['question']}")
            print(f"Expected: {q.get('expected_answer_hint', '—')}")
            print()
            print(f"DeepParser ({dp_rec.get('latency_ms', '?')}ms):")
            print(f"  {_truncate(dp_rec.get('answer'))}")
            if dp_rec.get("error"):
                print(f"  ERROR: {dp_rec['error']}")
            print()
            print(f"LlamaIndex ({li_rec.get('latency_ms', '?')}ms):")
            print(f"  {_truncate(li_rec.get('answer'))}")
            if li_rec.get("error"):
                print(f"  ERROR: {li_rec['error']}")
            print()

            while True:
                choice = input("Winner [d/l/t/s/q]: ").strip().lower()
                if choice in ("d", "l", "t", "s", "q"):
                    break
                print("  Enter d, l, t, s, or q")

            if choice == "q":
                print("Saving and quitting...")
                break
            if choice == "s":
                continue

            winner = {"d": "deepparser", "l": "llamaindex", "t": "tie"}[choice]
            scores[qid] = {
                "doc_id": doc_id,
                "category": category,
                "question": q["question"],
                "winner": winner,
                "dp_answer": dp_rec.get("answer"),
                "li_answer": li_rec.get("answer"),
                "dp_latency_ms": dp_rec.get("latency_ms"),
                "li_latency_ms": li_rec.get("latency_ms"),
            }
            _save_scores(scores)

    except KeyboardInterrupt:
        print("\n\nInterrupted — progress saved.")

    return scores


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(qa_pairs: dict, scores: dict) -> str:
    if not scores:
        return "No scored pairs yet. Run `python benchmark/score.py` to label answers."

    # Aggregate by category
    cat_stats: dict[str, dict] = defaultdict(lambda: {"dp": 0, "li": 0, "tie": 0, "total": 0})
    overall = {"dp": 0, "li": 0, "tie": 0, "total": 0}

    latencies_dp: list[int] = []
    latencies_li: list[int] = []

    for qid, s in scores.items():
        cat = s.get("category", "unknown")
        winner = s["winner"]
        cat_stats[cat][winner if winner in ("deepparser", "llamaindex") else "tie"] += 1
        cat_stats[cat]["total"] += 1
        overall[winner if winner in ("deepparser", "llamaindex") else "tie"] += 1
        overall["total"] += 1
        if s.get("dp_latency_ms"):
            latencies_dp.append(s["dp_latency_ms"])
        if s.get("li_latency_ms"):
            latencies_li.append(s["li_latency_ms"])

    total = overall["total"]
    dp_wins = overall["deepparser"]
    li_wins = overall["llamaindex"]
    ties = overall["tie"]
    win_rate = dp_wins / total * 100 if total else 0

    def pct(n: int, d: int) -> str:
        return f"{n/d*100:.0f}%" if d else "—"

    def avg_ms(lst: list[int]) -> str:
        return f"{sum(lst) // len(lst)}ms" if lst else "—"

    lines: list[str] = []
    lines.append("# DeepParser vs LlamaIndex Benchmark")
    lines.append("")
    lines.append(f"**{total} Q&A pairs** across {len(qa_pairs['docs'])} documents")
    lines.append("")
    lines.append("## Overall Results")
    lines.append("")
    lines.append("| System | Wins | Win Rate | Avg Answer Latency |")
    lines.append("|--------|------|----------|--------------------|")
    lines.append(f"| **DeepParser** | {dp_wins} | **{pct(dp_wins, total)}** | {avg_ms(latencies_dp)} |")
    lines.append(f"| LlamaIndex | {li_wins} | {pct(li_wins, total)} | {avg_ms(latencies_li)} |")
    lines.append(f"| Tie | {ties} | {pct(ties, total)} | — |")
    lines.append("")

    threshold = 70
    verdict = "✅ MOAT VALIDATED" if win_rate >= threshold else f"❌ Below {threshold}% threshold ({win_rate:.0f}%)"
    lines.append(f"**DeepParser win rate: {win_rate:.1f}%** — {verdict}")
    lines.append("")
    lines.append("## Results by Document Category")
    lines.append("")
    lines.append("| Category | Questions | DeepParser | LlamaIndex | Tie | DP Win Rate |")
    lines.append("|----------|-----------|------------|------------|-----|-------------|")

    cat_order = ["excel_pdf", "dwg", "scanned_pdf"]
    cat_labels = {
        "excel_pdf": "Excel-embedded PDF",
        "dwg": "DWG / CAD drawing",
        "scanned_pdf": "Scanned PDF",
    }
    for cat in cat_order:
        if cat not in cat_stats:
            continue
        s = cat_stats[cat]
        label = cat_labels.get(cat, cat)
        lines.append(
            f"| {label} | {s['total']} | {s['deepparser']} | {s['llamaindex']} | {s['tie']} | {pct(s['deepparser'], s['total'])} |"
        )

    lines.append("")
    lines.append("## Latency Summary")
    lines.append("")
    lines.append("| System | Avg Answer Latency | Samples |")
    lines.append("|--------|--------------------|---------|")
    lines.append(f"| DeepParser | {avg_ms(latencies_dp)} | {len(latencies_dp)} |")
    lines.append(f"| LlamaIndex | {avg_ms(latencies_li)} | {len(latencies_li)} |")
    lines.append("")
    lines.append("*DeepParser latency = parse (first call) + ask. LlamaIndex latency = query only (index build excluded).*")
    lines.append("")
    lines.append("## Methodology")
    lines.append("")
    lines.append("- 10 documents: 5 Excel-embedded PDF, 3 DWG/CAD, 2 scanned PDF")
    lines.append("- 5 questions per document = 50 Q&A pairs")
    lines.append("- LlamaIndex: `SimpleDirectoryReader` + `VectorStoreIndex`, default OpenAI embeddings, pinned to v0.12.x")
    lines.append("- Scoring: human-labeled (founder) — D=DeepParser wins, L=LlamaIndex wins, T=tie")
    lines.append("- Win threshold for moat validation: ≥70% on complex-format docs")
    lines.append("")
    lines.append(f"*Generated by `benchmark/score.py`. Scored pairs: {total}/{50}*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Score benchmark results")
    parser.add_argument("--report", action="store_true", help="Print report only, no interactive prompts")
    args = parser.parse_args()

    with open(QA_PAIRS_FILE) as f:
        qa_pairs = json.load(f)

    dp = _load_jsonl(DEEPPARSER_FILE)
    li = _load_jsonl(LLAMAINDEX_FILE)
    scores = _load_scores()

    if not args.report:
        scores = label_pairs(qa_pairs, dp, li, scores)

    report = generate_report(qa_pairs, scores)
    print("\n" + report)

    REPORT_FILE.write_text(report)
    print(f"\nReport saved → {REPORT_FILE}")

    # Also write a compact JSON summary for programmatic use
    total = len(scores)
    dp_wins = sum(1 for s in scores.values() if s["winner"] == "deepparser")
    summary = {
        "total": total,
        "deepparser_wins": dp_wins,
        "llamaindex_wins": sum(1 for s in scores.values() if s["winner"] == "llamaindex"),
        "ties": sum(1 for s in scores.values() if s["winner"] == "tie"),
        "deepparser_win_rate": round(dp_wins / total, 4) if total else 0,
        "moat_validated": (dp_wins / total >= 0.70) if total else False,
        "scored_pairs": total,
        "total_pairs": 50,
    }
    summary_path = RESULTS_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary saved → {summary_path}")


if __name__ == "__main__":
    main()
