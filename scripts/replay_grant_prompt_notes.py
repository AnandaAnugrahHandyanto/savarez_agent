#!/usr/bin/env python3
"""Replay real Grant notes through the grant-auto-review prompt renderer."""

from gateway.config import PlatformConfig
from gateway.platforms.webhook import WebhookAdapter

REAL_NOTES = {
    "kn789b00st6vp2hjfyxt5tqzs987fgxh": """<!-- grant-verdict:2026-05-26T15:05:00Z:CHANGES_REQUIRED -->

Terminal allowlist (Gate 1) is shipped cleanly on main at 5c8e675d6 and works as specified: tools/approval.py:884-997 implements _is_webhook_readonly_terminal_command(), the hardline floor still runs first (line 1199-1202), shell control operators are rejected, curl is method+host gated, and python/node -c blocks subprocess/child_process. All 3 new tests in tests/tools/test_approval.py::TestWebhookReadonlyAllowlist pass (verified locally). Config block is live at ~/.hermes/config.yaml under safety.webhook_allowlist.

Gate 2 (outbound-to-human allowlist) is NOT addressed. The internal_destinations config list is consumed only by the curl branch of the terminal allowlist, never by send_message_tool.py or any gateway platform adapter. Codebase-wide grep for 'outbound to human', 'blocked by safety gate', 'Holding. Stopping all other actions' returns zero matches in source. The gateway.log evidence at 08:47:56 cited in the card is the agent's own assistant-message text (a model self-imposed refusal), not a real Hermes code-level gate firing. AC smoke tests 2 and 4 therefore can't be verified as written because they presuppose a send_message gate that doesn't exist.

To close: (a) confirm in a follow-up commit or comment that Gate 2 was a model-layer refusal not a code-level gate, document that the existing send_message path has no outbound-to-human approval to allowlist against, and update or strike the Gate 2 portion of AC + smoke tests 2/4; OR (b) actually ship a send_message-level destination allowlist that consumes safety.webhook_allowlist.internal_destinations and add a smoke test for the external Discord case. Lightest path is (a), the real-world unblock (terminal allowlist) is already shipped and the 3 stuck cards this morning will move.

Reid completion: safety webhook allowlist shipped in commit 5c8e675d6, tests pass.
""",
    "kn74mkyw3typyvykjgxpe47spn87f9vt": """<!-- grant-verdict:2026-05-26T13:05:00Z:CHANGES_REQUIRED -->

CHANGES_REQUIRED. Original 7 AC all verified clean: script at /Users/TJ/hermes-workspace/Lex-Workspace/scripts/discipline-gap-card-filer.py is executable and stdlib-only; dry-run with state file present returns `{created:[], skipped:[3 titles], candidate_count:3}` confirming idempotent week-bucket dedupe; cron job 033a017062ed registered via Hermes (21:30 ET, 30 min after audit cc24e88bbe6b); 14-day backfill produced the three expected MC cards (kn76n5f.../decisions-2026-05, kn7avbj.../memory-curated, kn77tepd.../learnings-promoted), all in status=overnight, agent=lex, with `auto-filed` + `discipline-gap` tags; dedup state at ~/.hermes/state/discipline-gap-cards.json holds the three sha256 signatures with card_id + filed_at; brain note exists at concepts/discipline-gap-auto-filing with full provenance. Pitfalls handled correctly: week-bucket signatures (sha256("stale:{slug}:{iso-week}")) not day-bucket so daily reruns don't spam; discipline_gaps parsed defensively as strings via parse_gap_string; correction_samples filtered to recorded_within_24h==False only.

The gap: the folded auto-clear AC from kn7c8gzc28 ("when a flagged synthesis page is refreshed, the next night's run AUTO-ARCHIVES any open MC cards it filed for that slug") is NOT implemented. build_cards() only emits new GapCards for currently-flagged slugs; there is no inverse pass that walks state.filed_signatures, checks whether the slug is still in the latest run's discipline_gaps set, and POSTs tasks:archive for the card_id when the page has self-healed. Without that pass, the three cards filed tonight will persist in `overnight` even after Lex appends to the synthesis pages, and Lex has to remember to flip them done manually, exactly the "discipline-not-enforcement" failure mode this card was built to kill.

Fix scope for Reid (small, ~20 lines): after the create loop in main(), build `still_flagged_signatures = {hashlib.sha256(f"stale:{slug}:{iso_week_bucket(now_utc())}".encode()).hexdigest() for slug in latest_flagged_slugs(rows)}`, then iterate `state["filed_signatures"]` and for any signature in state but NOT in still_flagged_signatures (and not already archived), call `tasks:archive` via the same node scripts/file-card path or via direct curl to mellow-mule-232 prod, then mark `archived_at` in the state entry to prevent double-archive. Add a `--no-archive` flag for safety during the first soak night. Smoke: run filer, manually `touch` one of the synthesis pages, rerun filer, confirm the corresponding kn... card flips to archived and state entry gains `archived_at`.

Reid follow-up: inverse auto-archive shipped in commit 3076daa66, live smoke verified.
""",
}


def main() -> int:
    adapter = WebhookAdapter(
        PlatformConfig(enabled=True, extra={"secret": "test-global-secret"})
    )
    ok = True
    for task_id, notes in REAL_NOTES.items():
        rendered = adapter._render_prompt(
            "Task notes:\n{notes}",
            {"notes": notes},
            "convex.task.in_review",
            "grant-auto-review",
        )
        body = rendered.split("\n\n", 1)[1] if "\n\n" in rendered else rendered
        no_marker = "<!-- grant-verdict:" not in body
        no_verdict = "CHANGES_REQUIRED" not in body
        has_fresh_prefix = rendered.startswith("NOTE: Card has been re-submitted")
        ok = ok and no_marker and no_verdict and has_fresh_prefix
        print(f"{task_id}:")
        print(f"  fresh_prefix={has_fresh_prefix}")
        print(f"  marker_leaked={not no_marker}")
        print(f"  verdict_text_leaked={not no_verdict}")
        print(f"  rendered_tail={body.strip()[-180:]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
