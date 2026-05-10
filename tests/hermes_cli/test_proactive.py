import json
import sys
import time
import types

from hermes_cli import proactive


def test_build_reflection_prompt_is_safe_and_silent_by_default():
    prompt = proactive.build_reflection_prompt(
        lookback_days=5,
        max_sessions=12,
        min_confidence="high",
    )

    assert "Proactive signal scan" in prompt
    assert "last 5 days" in prompt
    assert "up to 12" in prompt
    assert "[SILENT]" in prompt
    assert "at most one proactive message" in prompt
    assert "NEVER send anything outside Hermes/the configured delivery system" in prompt
    assert "Drafting internally is allowed" in prompt
    assert "Ask before" in prompt
    assert "high confidence" in prompt
    assert "personal assistant" in prompt
    assert "Proactive modes" in prompt
    assert "meeting notes" in prompt
    assert "Silence is the correct answer unless the best candidate clears the bar" in prompt
    assert "No generic summaries, status theater" in prompt
    assert "meta-Hermes" in prompt
    assert "WFG/source quality shifts" in prompt
    assert "smart question" in prompt
    assert "family/personal logistics" in prompt
    assert "Would Charles plausibly reply" in prompt


def test_collect_proactive_signals_returns_structured_scan(monkeypatch):
    now = time.time()

    class FakeDB:
        def list_sessions_rich(self, **kwargs):
            return [
                {
                    "id": "s1",
                    "source": "telegram",
                    "title": "Sales meeting notes",
                    "last_active": now,
                    "preview": "Charles added meeting notes with a sales-team speech",
                }
            ]

        def search_messages(self, query, **kwargs):
            if "meeting notes" in query:
                return [
                        {
                            "session_id": "s1",
                            "source": "telegram",
                            "timestamp": now,
                            "content": "meeting notes included a sales team speech and delivery coaching opportunity",
                            "snippet": "meeting notes included a sales team speech and delivery coaching opportunity",
                        }
                ]
            if "OwnerPath" in query:
                return [
                        {
                            "session_id": "s2",
                            "source": "telegram",
                            "timestamp": now,
                            "content": "OwnerPath is on hold; do not nudge",
                            "snippet": "OwnerPath is on hold; do not nudge",
                        }
                ]
            return []

    monkeypatch.setitem(sys.modules, "hermes_state", types.SimpleNamespace(SessionDB=FakeDB))
    monkeypatch.setattr(
        proactive,
        "list_jobs",
        lambda include_disabled=True: [
            {"id": "j1", "name": "Broken cron", "last_error": "boom", "state": "scheduled"}
        ],
    )

    report = proactive.collect_proactive_signals(lookback_days=2, max_sessions=5)

    assert report["wakeAgent"] is True
    assert report["recent_sessions"][0]["id"] == "s1"
    assert {s["kind"] for s in report["signals"]} >= {"content_opportunity", "cron_failure"}
    assert report["suppressed_topics"]
    rendered = proactive.render_signal_scan(report)
    assert "## Proactive signal scan" in rendered
    assert json.loads(rendered.splitlines()[-1]) == {"wakeAgent": True}


def test_collect_proactive_signals_ignores_meta_proactivity_chatter(monkeypatch):
    now = time.time()

    class FakeDB:
        def list_sessions_rich(self, **kwargs):
            return [
                {
                    "id": "meta-session",
                    "source": "telegram",
                    "title": "Making Hermes proactive",
                    "last_active": now,
                    "preview": "Add More Info and Not useful feedback buttons",
                }
            ]

        def search_messages(self, query, **kwargs):
            if "want me" in query or "More Info" in query:
                return [
                    {
                        "session_id": "meta-session",
                        "source": "telegram",
                        "timestamp": now,
                        "snippet": "Add Do it, More Info, Not useful, and Don't nudge this buttons to proactive messages",
                    }
                ]
            return []

    monkeypatch.setitem(sys.modules, "hermes_state", types.SimpleNamespace(SessionDB=FakeDB))
    monkeypatch.setattr(proactive, "list_jobs", lambda include_disabled=True: [])

    report = proactive.collect_proactive_signals(lookback_days=2, max_sessions=5)

    assert report["signals"] == []
    assert report["wakeAgent"] is False


def test_collect_proactive_signals_surfaces_profile_decisions(tmp_path, monkeypatch):
    (tmp_path / "proactive-state.md").write_text(
        "# State\n\n## Blocked / Needs Decision\n- Choose whether to ship the dashboard as a draft PR or split it first.\n",
        encoding="utf-8",
    )
    (tmp_path / "HEARTBEAT.md").write_text("Ask smart questions when useful.", encoding="utf-8")

    class FakeDB:
        def list_sessions_rich(self, **kwargs):
            return []

        def search_messages(self, query, **kwargs):
            return []

    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "hermes_state", types.SimpleNamespace(SessionDB=FakeDB))
    monkeypatch.setattr(proactive, "list_jobs", lambda include_disabled=True: [])

    report = proactive.collect_proactive_signals(lookback_days=2, max_sessions=5)

    assert report["wakeAgent"] is True
    assert report["assistant_context"]["proactive_state"]
    assert report["signals"][0]["kind"] == "state_decision_needed"
    assert report["signals"][0]["mode"] == "ask_smart_question"
    assert "dashboard" in report["signals"][0]["excerpt"]


def test_collect_proactive_signals_ranks_cron_failures_over_content(monkeypatch):
    now = time.time()

    class FakeDB:
        def list_sessions_rich(self, **kwargs):
            return []

        def search_messages(self, query, **kwargs):
            if "meeting notes" in query:
                return [
                    {
                        "session_id": "content",
                        "source": "telegram",
                        "timestamp": now,
                        "snippet": "meeting notes include a decent content opportunity",
                    }
                ]
            return []

    monkeypatch.setitem(sys.modules, "hermes_state", types.SimpleNamespace(SessionDB=FakeDB))
    monkeypatch.setattr(proactive, "list_jobs", lambda include_disabled=True: [
        {"id": "bad", "name": "Broken job", "last_error": "delivery failed", "state": "scheduled"}
    ])

    report = proactive.collect_proactive_signals(lookback_days=2, max_sessions=5)

    assert report["signals"][0]["kind"] == "cron_failure"
    assert {signal["kind"] for signal in report["signals"]} >= {"cron_failure", "content_opportunity"}


def test_collect_proactive_signals_loads_profile_local_custom_signals(tmp_path, monkeypatch):
    signal_dir = tmp_path / "proactive"
    signal_dir.mkdir()
    (signal_dir / "signals.json").write_text(
        json.dumps(
            {
                "signals": [
                    {
                        "kind": "calendar_question",
                        "area": "calendar",
                        "mode": "ask_smart_question",
                        "reason": "upcoming meeting needs a prep choice",
                        "excerpt": "Tomorrow's ops meeting has no agenda; ask whether to draft a 3-bullet prep note.",
                        "score": 88,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeDB:
        def list_sessions_rich(self, **kwargs):
            return []

        def search_messages(self, query, **kwargs):
            return []

    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "hermes_state", types.SimpleNamespace(SessionDB=FakeDB))
    monkeypatch.setattr(proactive, "list_jobs", lambda include_disabled=True: [])

    report = proactive.collect_proactive_signals(lookback_days=2, max_sessions=5)

    assert report["signals"][0]["kind"] == "calendar_question"
    assert report["signals"][0]["area"] == "calendar"
    assert "ops meeting" in report["signals"][0]["excerpt"]


def test_proactive_ledger_suppresses_recently_nudged_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    now = 1_700_000_000.0
    report = {
        "wakeAgent": True,
        "signals": [
            {
                "kind": "content_opportunity",
                "mode": "offer_to_produce",
                "reason": "fresh notes",
                "session_id": "s1",
                "source": "telegram",
                "excerpt": "meeting notes included a sales speech critique opportunity",
            }
        ],
        "suppressed_topics": [],
        "scan_errors": [],
    }

    nudge = proactive.record_proactive_nudge(
        job={"id": "job1", "name": proactive.DEFAULT_JOB_NAME},
        message="Want me to polish the strongest two X drafts?",
        scan_report=report,
        now=now,
    )
    filtered = proactive.apply_ledger_filters(report, now=now + 60)

    assert nudge["id"]
    assert filtered["signals"] == []
    assert filtered["wakeAgent"] is False
    assert filtered["suppressed_by_ledger"][0]["nudge_id"] == nudge["id"]


def test_proactive_feedback_more_info_later_and_do_not_nudge(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    report = {
        "signals": [
            {
                "kind": "blocker_or_waiting",
                "mode": "ask_or_checked",
                "reason": "possible blocker",
                "session_id": "s2",
                "source": "telegram",
                "excerpt": "TestFlight blocked until Xcode ready",
            }
        ],
        "suppressed_topics": [],
        "scan_errors": [],
    }
    nudge = proactive.record_proactive_nudge(
        job={"id": "job2", "name": proactive.DEFAULT_JOB_NAME},
        message="TestFlight is still blocked. Want me to continue once Xcode is ready?",
        scan_report=report,
        now=1_700_000_000.0,
    )

    more = proactive.handle_proactive_feedback(nudge["id"], "more", now=1_700_000_010.0)
    assert more["ok"] is True
    assert "Why this surfaced" in more["followup"]
    assert "TestFlight blocked" in more["followup"]

    later = proactive.handle_proactive_feedback(nudge["id"], "later", now=1_700_000_020.0)
    assert later["ok"] is True
    assert "snoozed" in later["ack"].lower()

    hidden = proactive.handle_proactive_feedback(nudge["id"], "dont", now=1_700_000_030.0)
    assert hidden["ok"] is True
    assert "won't nudge" in hidden["ack"].lower()
    filtered = proactive.apply_ledger_filters(report, now=1_700_000_040.0)
    assert filtered["signals"] == []


def test_proactive_do_it_feedback_builds_safe_agent_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    nudge = proactive.record_proactive_nudge(
        job={"id": "job3", "name": proactive.DEFAULT_JOB_NAME},
        message="Want me to polish the strongest two X drafts?",
        scan_report={
            "signals": [
                {
                    "kind": "content_opportunity",
                    "mode": "offer_to_produce",
                    "reason": "fresh notes/content may create a useful draft",
                    "session_id": "s3",
                    "source": "telegram",
                    "excerpt": "sales-meeting speech critique and X drafts are ready",
                }
            ]
        },
        now=1_700_000_000.0,
    )

    result = proactive.handle_proactive_feedback(nudge["id"], "do", now=1_700_000_001.0)

    assert result["ok"] is True
    assert "starting" in result["ack"].lower()
    assert "agent_prompt" in result
    assert "User tapped Do it" in result["agent_prompt"]
    assert "Do not send, post, email" in result["agent_prompt"]


def test_render_signal_scan_wake_gate_can_skip_agent():
    rendered = proactive.render_signal_scan({"wakeAgent": False, "signals": []})
    assert rendered == '{"wakeAgent": false}'


def test_install_creates_idempotent_cron_job(monkeypatch):
    calls = []
    jobs = []

    def fake_list_jobs(include_disabled=True):
        return list(jobs)

    def fake_create_job(**kwargs):
        calls.append(("create", kwargs))
        job = {
            "id": "abc123",
            "name": kwargs["name"],
            "prompt": kwargs["prompt"],
            "schedule_display": kwargs["schedule"],
            "deliver": kwargs["deliver"],
            "script": kwargs["script"],
            "enabled_toolsets": kwargs["enabled_toolsets"],
            "state": "scheduled",
        }
        jobs.append(job)
        return job

    def fake_update_job(job_id, updates):
        calls.append(("update", job_id, updates))
        jobs[0].update(updates)
        return dict(jobs[0])

    monkeypatch.setattr(proactive, "list_jobs", fake_list_jobs)
    monkeypatch.setattr(proactive, "create_job", fake_create_job)
    monkeypatch.setattr(proactive, "update_job", fake_update_job)
    monkeypatch.setattr(proactive, "_ensure_scanner_script", lambda: "proactive_signal_scan.py")

    first = proactive.install_proactive_job(
        schedule="0 9 * * *",
        deliver="telegram",
        lookback_days=3,
        max_sessions=20,
    )
    second = proactive.install_proactive_job(
        schedule="0 10 * * *",
        deliver="local",
        lookback_days=7,
        max_sessions=40,
    )

    assert first["action"] == "created"
    assert second["action"] == "updated"
    assert calls[0][0] == "create"
    created = calls[0][1]
    assert created["name"] == proactive.DEFAULT_JOB_NAME
    assert created["script"] == "proactive_signal_scan.py"
    assert created["enabled_toolsets"] == ["memory"]
    assert "last 3 days" in created["prompt"]
    assert created["deliver"] == "telegram"

    assert calls[1][0] == "update"
    assert calls[1][1] == "abc123"
    assert calls[1][2]["schedule"] == "0 10 * * *"
    assert calls[1][2]["deliver"] == "local"
    assert calls[1][2]["script"] == "proactive_signal_scan.py"
    assert "last 7 days" in calls[1][2]["prompt"]


def test_install_can_create_paused_job(monkeypatch):
    created_jobs = []
    updates = []

    monkeypatch.setattr(proactive, "list_jobs", lambda include_disabled=True: [])
    monkeypatch.setattr(proactive, "_ensure_scanner_script", lambda: "proactive_signal_scan.py")

    def fake_create_job(**kwargs):
        job = {"id": "paused1", "name": kwargs["name"], "state": "scheduled", "enabled": True}
        created_jobs.append(kwargs)
        return job

    def fake_update_job(job_id, update):
        updates.append((job_id, update))
        return {"id": job_id, **update}

    monkeypatch.setattr(proactive, "create_job", fake_create_job)
    monkeypatch.setattr(proactive, "update_job", fake_update_job)

    result = proactive.install_proactive_job(paused=True)

    assert result["action"] == "created_paused"
    assert updates == [("paused1", {"enabled": False, "state": "paused", "paused_reason": "created paused for review"})]
    assert created_jobs[0]["script"] == "proactive_signal_scan.py"


def test_cli_prompt_outputs_json_when_requested(capsys):
    rc = proactive.cmd_proactive(
        type(
            "Args",
            (),
            {
                "proactive_command": "prompt",
                "lookback_days": 2,
                "max_sessions": 9,
                "min_confidence": "medium",
                "json": True,
            },
        )()
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["lookback_days"] == 2
    assert payload["max_sessions"] == 9
    assert "medium confidence" in payload["prompt"]


def test_feedback_updates_adaptive_preferences_and_reranks_future_signals(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    now = 1_700_000_000.0
    nudge = proactive.record_proactive_nudge(
        job={"id": "job-a", "name": proactive.DEFAULT_JOB_NAME},
        message="Want me to turn the meeting notes into a short coaching draft?",
        scan_report={
            "signals": [
                {
                    "kind": "content_opportunity",
                    "area": "content",
                    "mode": "offer_to_produce",
                    "reason": "accepted content draft pattern",
                    "source": "telegram",
                    "excerpt": "private meeting notes should not become global training text",
                    "score": 50,
                }
            ]
        },
        now=now,
    )

    proactive.handle_proactive_feedback(nudge["id"], "do", now=now + 1)
    prefs = proactive.load_proactive_preferences()

    assert prefs["kind_weights"]["content_opportunity"]["score_adjustment"] > 0
    assert prefs["kind_weights"]["content_opportunity"]["accepted"] == 1

    report = {
        "wakeAgent": True,
        "signals": [
            {"kind": "content_opportunity", "area": "content", "mode": "offer_to_produce", "excerpt": "content", "score": 50},
            {"kind": "decision_needed", "area": "decisions", "mode": "ask_smart_question", "excerpt": "decision", "score": 52},
        ],
    }
    adapted = proactive.apply_adaptive_preferences(report)

    assert adapted["signals"][0]["kind"] == "content_opportunity"
    assert adapted["signals"][0]["adaptive_score_adjustment"] > 0


def test_negative_feedback_tunes_down_future_signals_without_mutating_raw_report(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    now = 1_700_000_000.0
    nudge = proactive.record_proactive_nudge(
        job={"id": "job-b", "name": proactive.DEFAULT_JOB_NAME},
        message="Want me to draft content from this?",
        scan_report={
            "signals": [
                {
                    "kind": "content_opportunity",
                    "area": "content",
                    "mode": "offer_to_produce",
                    "reason": "weak content idea",
                    "source": "telegram",
                    "excerpt": "private draft context",
                    "score": 80,
                }
            ]
        },
        now=now,
    )

    proactive.handle_proactive_feedback(nudge["id"], "not", now=now + 1)
    report = {"wakeAgent": True, "signals": [{"kind": "content_opportunity", "area": "content", "excerpt": "new item", "score": 80}]}
    adapted = proactive.apply_adaptive_preferences(report)

    assert report["signals"][0]["score"] == 80
    assert adapted["signals"][0]["score"] < 80
    assert adapted["signals"][0]["adaptive_score_adjustment"] < 0


def test_self_evolution_report_proposes_bounded_changes_and_skill_candidates(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    now = 1_700_000_000.0
    for idx in range(3):
        nudge = proactive.record_proactive_nudge(
            job={"id": f"job-{idx}", "name": proactive.DEFAULT_JOB_NAME},
            message=f"Want me to prepare the WFG call-quality sample #{idx}?",
            scan_report={
                "signals": [
                    {
                        "kind": "source_quality_watch",
                        "area": "sales_ops",
                        "mode": "ask_to_investigate",
                        "reason": "accepted repeat workflow",
                        "source": "profile-local",
                        "excerpt": f"Sensitive WFG transcript detail #{idx}",
                        "suggested_action": "pull a transcript sample and classify source quality",
                        "score": 90,
                    }
                ]
            },
            now=now + idx,
        )
        proactive.handle_proactive_feedback(nudge["id"], "do", now=now + idx + 10)

    report = proactive.build_self_evolution_report(now=now + 86_400)

    assert report["summary"]["accepted"] == 3
    assert report["recommendations"]
    assert report["skill_proposals"]
    assert report["skill_proposals"][0]["action"] == "propose_skill"
    dumped = json.dumps(report)
    assert "Sensitive WFG transcript detail" not in dumped
    assert "Want me to prepare" not in dumped
    assert all(item["requires_user_approval"] for item in report["skill_proposals"])


def test_privacy_safe_learning_export_contains_only_aggregates(tmp_path, monkeypatch):
    monkeypatch.setattr(proactive, "get_hermes_home", lambda: tmp_path)
    nudge = proactive.record_proactive_nudge(
        job={"id": "job-private", "name": proactive.DEFAULT_JOB_NAME},
        message="Private TestFlight blocker for Charles involving internal paths",
        scan_report={
            "signals": [
                {
                    "kind": "blocker_or_waiting",
                    "area": "projects",
                    "mode": "ask_to_investigate",
                    "reason": "private blocker",
                    "source": "telegram",
                    "session_id": "secret-session-id",
                    "excerpt": "/Users/bots/private/path and customer detail",
                }
            ]
        },
        now=1_700_000_000.0,
    )
    proactive.handle_proactive_feedback(nudge["id"], "do", now=1_700_000_001.0)

    export = proactive.export_privacy_safe_learning()
    dumped = json.dumps(export)

    assert export["privacy_safe"] is True
    assert export["totals"]["feedback"] == 1
    assert export["by_kind"]["blocker_or_waiting"]["do"] == 1
    assert "TestFlight" not in dumped
    assert "/Users/bots" not in dumped
    assert "secret-session-id" not in dumped
    assert "Private" not in dumped


def test_self_evolution_guardrails_reject_unsafe_or_private_changes():
    assert proactive.validate_self_evolution_change({"type": "kind_weight", "kind": "content_opportunity", "delta": 3})["ok"] is True
    assert proactive.validate_self_evolution_change({"type": "cooldown", "kind": "content_opportunity", "hours": 96})["ok"] is True

    unsafe = [
        {"type": "code_edit", "path": "run_agent.py"},
        {"type": "prompt_edit", "text": "silently change the live prompt"},
        {"type": "external_action", "target": "email"},
        {"type": "kind_weight", "kind": "content", "raw_text": "private user text"},
    ]
    for change in unsafe:
        result = proactive.validate_self_evolution_change(change)
        assert result["ok"] is False
        assert result["requires_user_approval"] is True
