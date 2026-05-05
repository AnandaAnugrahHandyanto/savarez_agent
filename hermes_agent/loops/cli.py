"""Fire-based CLI for UCPM-specific hermes-agent commands.

Registered as the `hermes-ucpm` console script (see pyproject.toml). Kept
in its own entry point so it can evolve independently of the upstream
`hermes` CLI defined in `hermes_cli/main.py` — that file gets rebased
from upstream and we don't want UCPM commands sitting on top of it.

Usage examples:

    uv run hermes-ucpm test-property-loop \\
        --inbox ./inbox \\
        --outbox ./outbox \\
        --audit ./audit-log \\
        --company-dir ../paperclip-UCPM/companies/1011-verrado-office

    uv run hermes-ucpm --help
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

import fire

from .property_test_loop import LoopRunSummary, run_loop


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


class HermesUcpmCli:
    """Top-level UCPM commands."""

    def test_property_loop(
        self,
        inbox: str = "./inbox",
        outbox: str = "./outbox",
        audit: str = "./audit-log",
        company_dir: str = "../paperclip-UCPM/companies/ucpm-default",
        property_id: Optional[str] = None,
        verbose: bool = False,
    ) -> int:
        """Run P-01 + P-02 over the inbox and write drafts + audit logs.

        Args:
            inbox: directory of `*.json` inbound messages.
            outbox: parent directory; drafts written to `<outbox>/drafts/`.
            audit: directory for `<msg_id>.jsonl` audit logs.
            company_dir: per-property company directory under
                `paperclip-UCPM/companies/`. Defaults to `ucpm-default`.
            property_id: optional override for the audit `property_id`
                column (defaults to the company-dir basename).
            verbose: enable DEBUG logging.

        Returns:
            0 on full success, 1 if any messages were skipped (malformed
            input or runtime error). Per-message failures don't crash the
            loop — they're captured in the summary.
        """
        _setup_logging(verbose)

        summary = run_loop(
            inbox_dir=Path(inbox),
            outbox_dir=Path(outbox),
            audit_dir=Path(audit),
            company_dir=Path(company_dir),
            property_id=property_id,
        )
        _print_summary(summary)
        return 0 if not summary.skipped else 1


def _print_summary(summary: LoopRunSummary) -> None:
    print(f"Processed: {len(summary.processed)}")
    for r in summary.processed:
        gates = ",".join(r.gates_triggered) if r.gates_triggered else "-"
        urgency = r.triage.urgency if r.triage else "-"
        print(
            f"  {r.msg_id}: intent={r.classification.intent} "
            f"urgency={urgency} gates={gates} "
            f"human_attention={r.human_attention_required} "
            f"-> {r.draft_path}"
        )
    if summary.skipped:
        print(f"Skipped: {len(summary.skipped)}")
        for path, reason in summary.skipped:
            print(f"  {path.name}: {reason}")
    print(f"LLM calls: {summary.llm_calls}")


def main() -> None:
    """Entry point referenced from pyproject.toml [project.scripts]."""
    fire.Fire(HermesUcpmCli, name="hermes-ucpm")


if __name__ == "__main__":  # pragma: no cover
    main()
    sys.exit(0)
