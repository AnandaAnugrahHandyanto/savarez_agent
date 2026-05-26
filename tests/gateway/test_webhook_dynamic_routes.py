"""Tests for webhook adapter dynamic route loading."""

import json
import os
import pytest
from pathlib import Path

from gateway.config import PlatformConfig
from gateway.platforms.webhook import (
    WebhookAdapter,
    _DYNAMIC_ROUTES_FILENAME,
    _GRANT_FRESH_AUDIT_INSTRUCTION,
    _INSECURE_NO_AUTH,
)


def _make_adapter(routes=None, extra=None):
    _extra = extra or {}
    if routes:
        _extra["routes"] = routes
    _extra.setdefault("secret", "test-global-secret")
    config = PlatformConfig(enabled=True, extra=_extra)
    return WebhookAdapter(config)


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))


class TestDynamicRouteLoading:
    def test_no_dynamic_file(self):
        adapter = _make_adapter(routes={"static": {"secret": "s"}})
        adapter._reload_dynamic_routes()
        assert "static" in adapter._routes
        assert len(adapter._dynamic_routes) == 0

    def test_loads_dynamic_routes(self, tmp_path):
        subs = {"my-hook": {"secret": "dynamic-secret", "prompt": "test", "events": []}}
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(json.dumps(subs))

        adapter = _make_adapter(routes={"static": {"secret": "s"}})
        adapter._reload_dynamic_routes()
        assert "my-hook" in adapter._routes
        assert "static" in adapter._routes

    def test_static_takes_precedence(self, tmp_path):
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"conflict": {"secret": "dynamic", "prompt": "dyn"}})
        )
        adapter = _make_adapter(routes={"conflict": {"secret": "static", "prompt": "stat"}})
        adapter._reload_dynamic_routes()
        assert adapter._routes["conflict"]["secret"] == "static"

    def test_mtime_gated(self, tmp_path):
        import time
        path = tmp_path / _DYNAMIC_ROUTES_FILENAME
        path.write_text(json.dumps({"v1": {"secret": "s"}}))

        adapter = _make_adapter()
        adapter._reload_dynamic_routes()
        assert "v1" in adapter._dynamic_routes

        # Same mtime — no reload
        adapter._dynamic_routes["injected"] = True
        adapter._reload_dynamic_routes()
        assert "injected" in adapter._dynamic_routes

        # New write — reloads
        time.sleep(0.05)
        path.write_text(json.dumps({"v2": {"secret": "s"}}))
        adapter._reload_dynamic_routes()
        assert "v2" in adapter._dynamic_routes
        assert "v1" not in adapter._dynamic_routes

    def test_file_removal_clears(self, tmp_path):
        path = tmp_path / _DYNAMIC_ROUTES_FILENAME
        path.write_text(json.dumps({"temp": {"secret": "s"}}))
        adapter = _make_adapter()
        adapter._reload_dynamic_routes()
        assert "temp" in adapter._dynamic_routes

        path.unlink()
        adapter._reload_dynamic_routes()
        assert len(adapter._dynamic_routes) == 0

    def test_corrupted_file(self, tmp_path):
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text("not json")
        adapter = _make_adapter(routes={"static": {"secret": "s"}})
        adapter._reload_dynamic_routes()
        assert "static" in adapter._routes
        assert len(adapter._dynamic_routes) == 0


class TestDynamicRouteSecretValidation:
    """Empty/missing secrets must be rejected during hot-reload.

    Regression for HMAC bypass: prior to the fix, an agent-induced
    dynamic route with `"secret": ""` would be merged into self._routes
    by _reload_dynamic_routes(), then _handle_webhook's
    `if secret and secret != _INSECURE_NO_AUTH` would skip signature
    validation because empty string is falsy. Unauthenticated POSTs
    would then execute the webhook prompt.
    """

    def test_empty_secret_rejected(self, tmp_path):
        # Explicit empty-string secret must NOT fall back to the global
        # secret, and the route must be skipped entirely.
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"evil": {"secret": "", "prompt": "rm -rf"}})
        )
        adapter = _make_adapter()  # has global secret
        adapter._reload_dynamic_routes()
        assert "evil" not in adapter._routes
        assert "evil" not in adapter._dynamic_routes

    def test_missing_secret_no_global_rejected(self, tmp_path):
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"orphan": {"prompt": "test"}})
        )
        # No global secret configured
        adapter = _make_adapter(extra={"secret": ""})
        adapter._reload_dynamic_routes()
        assert "orphan" not in adapter._routes
        assert "orphan" not in adapter._dynamic_routes

    def test_missing_secret_inherits_global(self, tmp_path):
        # No per-route secret but a global one is set → route is kept,
        # the global secret protects it. Preserves existing fallback.
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"valid": {"prompt": "ok"}})
        )
        adapter = _make_adapter()  # global secret set
        adapter._reload_dynamic_routes()
        assert "valid" in adapter._routes

    def test_insecure_no_auth_preserved(self, tmp_path):
        # Explicit opt-in escape hatch for local testing — must still load.
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"test": {"secret": _INSECURE_NO_AUTH, "prompt": "p"}})
        )
        adapter = _make_adapter(extra={"host": "127.0.0.1"})
        adapter._reload_dynamic_routes()
        assert "test" in adapter._routes

    def test_insecure_no_auth_rejected_on_non_loopback_bind(self, tmp_path):
        # Dynamic INSECURE_NO_AUTH routes are only valid on loopback hosts.
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"pub": {"secret": _INSECURE_NO_AUTH, "prompt": "p"}})
        )
        adapter = _make_adapter(extra={"host": "0.0.0.0"})
        adapter._reload_dynamic_routes()
        assert "pub" not in adapter._routes
        assert "pub" not in adapter._dynamic_routes

    def test_warning_logged_on_skip(self, tmp_path, caplog):
        import logging
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({"silent": {"secret": "", "prompt": "x"}})
        )
        adapter = _make_adapter()
        with caplog.at_level(logging.WARNING, logger="gateway.platforms.webhook"):
            adapter._reload_dynamic_routes()
        assert any("silent" in rec.message for rec in caplog.records)

    def test_partial_skip(self, tmp_path):
        # One route bad, one route good — only the bad one is dropped.
        (tmp_path / _DYNAMIC_ROUTES_FILENAME).write_text(
            json.dumps({
                "bad":  {"secret": "", "prompt": "x"},
                "good": {"secret": "valid-secret", "prompt": "y"},
            })
        )
        adapter = _make_adapter()
        adapter._reload_dynamic_routes()
        assert "good" in adapter._routes
        assert "bad" not in adapter._routes


class TestGrantAutoReviewPromptRendering:
    def test_zero_markers_noop(self):
        adapter = _make_adapter()
        template = "Review {title}\n\nNo prior verdict."

        rendered = adapter._render_prompt(
            template,
            {"title": "card"},
            "convex.task.in_review",
            "grant-auto-review",
        )

        assert rendered == "Review card\n\nNo prior verdict."
        assert not rendered.startswith(_GRANT_FRESH_AUDIT_INSTRUCTION)

    def test_one_marker_strips_and_prefixes(self):
        adapter = _make_adapter()
        template = (
            "Before\n"
            "<!-- grant-verdict:2026-05-26T15:05:00Z:CHANGES_REQUIRED -->\n"
            "Old verdict text"
        )

        rendered = adapter._render_prompt(
            template,
            {},
            "convex.task.in_review",
            "grant-auto-review",
        )

        assert rendered.startswith(_GRANT_FRESH_AUDIT_INSTRUCTION)
        assert "Before" in rendered
        assert "grant-verdict" not in rendered
        assert "Old verdict text" not in rendered

    def test_two_markers_strip_both_and_prefix(self):
        adapter = _make_adapter()
        template = (
            "Before\n"
            "<!-- grant-verdict:2026-05-26T15:05:00Z:CHANGES_REQUIRED -->\n"
            "Old verdict one\n"
            "<!-- grant-verdict:2026-05-26T16:05:00Z:CHANGES_REQUIRED -->\n"
            "Old verdict two"
        )

        rendered = adapter._render_prompt(
            template,
            {},
            "convex.task.in_review",
            "grant-auto-review",
        )

        assert rendered.startswith(_GRANT_FRESH_AUDIT_INSTRUCTION)
        assert "Before" in rendered
        assert "grant-verdict" not in rendered
        assert "Old verdict one" not in rendered
        assert "Old verdict two" not in rendered

    def test_non_grant_auto_review_route_no_change(self):
        adapter = _make_adapter()
        template = (
            "Before\n"
            "<!-- grant-verdict:2026-05-26T15:05:00Z:CHANGES_REQUIRED -->\n"
            "Old verdict text"
        )

        rendered = adapter._render_prompt(
            template,
            {},
            "convex.task.in_review",
            "other-route",
        )

        assert rendered == template
        assert not rendered.startswith(_GRANT_FRESH_AUDIT_INSTRUCTION)

    def test_single_marker_preserves_trailing_post_verdict_text(self):
        adapter = _make_adapter()
        template = (
            "Before\n"
            "<!-- grant-verdict:2026-05-26T15:05:00Z:CHANGES_REQUIRED -->\n"
            "Old verdict text\n\n"
            "POST-VERDICT REID SIGNAL: commit abc123 fixed the gap"
        )

        rendered = adapter._render_prompt(
            template,
            {},
            "convex.task.in_review",
            "grant-auto-review",
        )

        assert rendered.startswith(_GRANT_FRESH_AUDIT_INSTRUCTION)
        assert "Before" in rendered
        assert "POST-VERDICT REID SIGNAL: commit abc123 fixed the gap" in rendered
        assert "grant-verdict" not in rendered
        assert "Old verdict text" not in rendered

    @pytest.mark.parametrize(
        "notes",
        [
            """<!-- grant-verdict:2026-05-26T15:05:00Z:CHANGES_REQUIRED -->

Terminal allowlist (Gate 1) is shipped cleanly on main at 5c8e675d6 and works as specified: tools/approval.py:884-997 implements _is_webhook_readonly_terminal_command(), the hardline floor still runs first (line 1199-1202), shell control operators are rejected, curl is method+host gated, and python/node -c blocks subprocess/child_process. All 3 new tests in tests/tools/test_approval.py::TestWebhookReadonlyAllowlist pass (verified locally). Config block is live at ~/.hermes/config.yaml under safety.webhook_allowlist.

Gate 2 (outbound-to-human allowlist) is NOT addressed. The internal_destinations config list is consumed only by the curl branch of the terminal allowlist, never by send_message_tool.py or any gateway platform adapter. Codebase-wide grep for 'outbound to human', 'blocked by safety gate', 'Holding. Stopping all other actions' returns zero matches in source. The gateway.log evidence at 08:47:56 cited in the card is the agent's own assistant-message text (a model self-imposed refusal), not a real Hermes code-level gate firing. AC smoke tests 2 and 4 therefore can't be verified as written because they presuppose a send_message gate that doesn't exist.

To close: (a) confirm in a follow-up commit or comment that Gate 2 was a model-layer refusal not a code-level gate, document that the existing send_message path has no outbound-to-human approval to allowlist against, and update or strike the Gate 2 portion of AC + smoke tests 2/4; OR (b) actually ship a send_message-level destination allowlist that consumes safety.webhook_allowlist.internal_destinations and add a smoke test for the external Discord case. Lightest path is (a), the real-world unblock (terminal allowlist) is already shipped and the 3 stuck cards this morning will move.

Reid completion: safety webhook allowlist shipped in commit 5c8e675d6, tests pass.
""",
            """<!-- grant-verdict:2026-05-26T13:05:00Z:CHANGES_REQUIRED -->

CHANGES_REQUIRED. Original 7 AC all verified clean: script at /Users/TJ/hermes-workspace/Lex-Workspace/scripts/discipline-gap-card-filer.py is executable and stdlib-only; dry-run with state file present returns `{created:[], skipped:[3 titles], candidate_count:3}` confirming idempotent week-bucket dedupe; cron job 033a017062ed registered via Hermes (21:30 ET, 30 min after audit cc24e88bbe6b); 14-day backfill produced the three expected MC cards (kn76n5f.../decisions-2026-05, kn7avbj.../memory-curated, kn77tepd.../learnings-promoted), all in status=overnight, agent=lex, with `auto-filed` + `discipline-gap` tags; dedup state at ~/.hermes/state/discipline-gap-cards.json holds the three sha256 signatures with card_id + filed_at; brain note exists at concepts/discipline-gap-auto-filing with full provenance. Pitfalls handled correctly: week-bucket signatures (sha256("stale:{slug}:{iso-week}")) not day-bucket so daily reruns don't spam; discipline_gaps parsed defensively as strings via parse_gap_string; correction_samples filtered to recorded_within_24h==False only.

The gap: the folded auto-clear AC from kn7c8gzc28 ("when a flagged synthesis page is refreshed, the next night's run AUTO-ARCHIVES any open MC cards it filed for that slug") is NOT implemented. build_cards() only emits new GapCards for currently-flagged slugs; there is no inverse pass that walks state.filed_signatures, checks whether the slug is still in the latest run's discipline_gaps set, and POSTs tasks:archive for the card_id when the page has self-healed. Without that pass, the three cards filed tonight will persist in `overnight` even after Lex appends to the synthesis pages, and Lex has to remember to flip them done manually, exactly the "discipline-not-enforcement" failure mode this card was built to kill.

Fix scope for Reid (small, ~20 lines): after the create loop in main(), build `still_flagged_signatures = {hashlib.sha256(f"stale:{slug}:{iso_week_bucket(now_utc())}".encode()).hexdigest() for slug in latest_flagged_slugs(rows)}`, then iterate `state["filed_signatures"]` and for any signature in state but NOT in still_flagged_signatures (and not already archived), call `tasks:archive` via the same node scripts/file-card path or via direct curl to mellow-mule-232 prod, then mark `archived_at` in the state entry to prevent double-archive. Add a `--no-archive` flag for safety during the first soak night. Smoke: run filer, manually `touch` one of the synthesis pages, rerun filer, confirm the corresponding kn... card flips to archived and state entry gains `archived_at`.

Reid follow-up: inverse auto-archive shipped in commit 3076daa66, live smoke verified.
""",
        ],
    )
    def test_replay_real_notes_strips_prior_verdict_without_regurgitation(self, notes):
        adapter = _make_adapter()

        rendered = adapter._render_prompt(
            "Task notes:\n{notes}",
            {"notes": notes},
            "convex.task.in_review",
            "grant-auto-review",
        )

        assert rendered.startswith(_GRANT_FRESH_AUDIT_INSTRUCTION)
        body = rendered.removeprefix(_GRANT_FRESH_AUDIT_INSTRUCTION)
        assert "<!-- grant-verdict:" not in body
        assert "CHANGES_REQUIRED" not in body
        assert "Reid" in body
