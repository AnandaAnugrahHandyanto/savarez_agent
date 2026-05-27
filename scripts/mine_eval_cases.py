#!/usr/bin/env python3
"""Mine candidate eval cases from Hermes session/trajectory data.

Usage
-----

    # Mine from state.db (default)
    python scripts/mine_eval_cases.py --source state-db --limit 20

    # Mine failed trajectories
    python scripts/mine_eval_cases.py --source trajectories --failed-only

    # Export draft YAML cases
    python scripts/mine_eval_cases.py --source state-db --limit 10 --output evals/cases/drafts/

    # Full spec
    python scripts/mine_eval_cases.py \\
        --source state-db \\
        --source-filter cli \\
        --model gpt-5.4 \\
        --min-tool-calls 1 \\
        --min-tokens 100 \\
        --days-back 7 \\
        --limit 20 \\
        --output evals/cases/drafts/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so ``evals`` is importable
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from evals.mining import (
    candidate_to_draft_case,
    export_candidates_report,
    export_draft_cases,
    mine_from_cron_outputs,
    mine_from_session_db,
    mine_from_trajectories,
)

from hermes_constants import get_hermes_home  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mine candidate eval cases from Hermes traces and sessions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--source",
        choices=["state-db", "trajectories", "cron-outputs"],
        default="state-db",
        help="Data source to mine from (default: state-db)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of candidates to return (default: 50)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory for draft YAML case files. "
        "If set, writes individual YAML draft cases and a summary report. "
        "If omitted, prints a summary to stdout.",
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Only include sessions/trajectories that failed or ended with errors",
    )

    # state-db specific filters
    parser.add_argument(
        "--source-filter",
        type=str,
        default=None,
        help="Session source filter (e.g. 'cli', 'telegram')",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model name filter (LIKE match)",
    )
    parser.add_argument(
        "--min-tool-calls",
        type=int,
        default=0,
        help="Minimum tool_call_count for sessions (default: 0 = no filter)",
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=0,
        help="Minimum total tokens (input+output) for sessions (default: 0)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="Only include sessions started within this many days (default: all)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="Explicit path to state.db (default: ~/.hermes/state.db)",
    )
    parser.add_argument(
        "--trajectories-path",
        type=str,
        default=None,
        help="Path to trajectory JSONL file (default: auto-detect from HERMES_HOME)",
    )
    parser.add_argument(
        "--cron-dir",
        type=str,
        default=None,
        help="Path to cron output directory (default: ~/.hermes/cron/output/)",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="Optional path for a markdown summary report (default: same as --output)",
    )

    return parser


def _resolve_default_paths() -> dict[str, Path]:
    hermes_home = get_hermes_home()
    return {
        "db_path": hermes_home / "state.db",
        "trajectories_path": hermes_home / "trajectories",
        "cron_dir": hermes_home / "cron" / "output",
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    defaults = _resolve_default_paths()

    # --- Run the appropriate miner ---
    if args.source == "state-db":
        db_path = args.db_path or str(defaults["db_path"])
        if not Path(db_path).exists():
            print(f"ERROR: session DB not found at {db_path}", file=sys.stderr)
            return 1
        result = mine_from_session_db(
            db_path,
            source=args.source_filter,
            model=args.model,
            failed_only=args.failed_only,
            min_tool_calls=args.min_tool_calls,
            min_tokens=args.min_tokens,
            days_back=args.days_back,
            limit=args.limit,
        )
    elif args.source == "trajectories":
        traj_path = args.trajectories_path or str(defaults["trajectories_path"])
        result = mine_from_trajectories(
            traj_path,
            failed_only=args.failed_only,
            limit=args.limit,
        )
    elif args.source == "cron-outputs":
        cron_dir = args.cron_dir or str(defaults["cron_dir"])
        result = mine_from_cron_outputs(
            cron_dir,
            limit=args.limit,
        )
    else:
        print(f"ERROR: unknown source {args.source!r}", file=sys.stderr)
        return 1

    # --- Output ---
    if args.output:
        out_dir = Path(args.output)
        files = export_draft_cases(
            result.candidates,
            output_dir=out_dir,
        )

        report_path = args.report or str(out_dir / "MINED_REPORT.md")
        export_candidates_report(result.candidates, report_path)

        print(f"Mined {len(result.candidates)} candidates from {args.source}")
        print(f"  Draft YAML cases: {len(files)} files in {out_dir}")
        print(f"  Summary report:   {report_path}")
        print(f"  Sessions scanned: {result.total_sessions_scanned}")
    else:
        # Print summary to stdout
        print(f"Source: {args.source}")
        print(f"Sessions scanned: {result.total_sessions_scanned}")
        print(f"Candidates mined: {result.total_candidates}")
        print()

        if not result.candidates:
            print("No candidates found matching the given filters.")
            return 0

        print(f"{'#':>3}  {'Candidate ID':<36} {'Model':<22} {'Tools':<24} {'Failed':<7} {'Reason'}")
        print("---  " + "-" * 35 + "  " + "-" * 21 + "  " + "-" * 23 + "  " + "-" * 6 + "  " + "------")
        for idx, c in enumerate(result.candidates, start=1):
            tool_str = ", ".join(c.tool_names[:3])
            if len(c.tool_names) > 3:
                tool_str += "..."
            print(
                f"{idx:>3}  {c.candidate_id:<36} {(c.model or '-'):<22} {tool_str:<24} "
                f"{'❌' if c.failed else '✅':<7} {c.reason or '-'}"
            )

        print()
        print(f"Run with --output <dir> to export draft YAML case files.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())