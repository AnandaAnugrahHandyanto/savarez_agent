from __future__ import annotations

from types import SimpleNamespace

from gateway.config import GatewayConfig, HomeChannel, Platform, PlatformConfig
from hermes_cli import kanban_db as kb


def _runner(monkeypatch, checkpoint_config=None, keywords=None):
    from gateway import run as gateway_run
    from gateway.run import GatewayRunner

    cfg = checkpoint_config or {
        "enabled": True,
        "platforms": ["discord"],
        "keywords": keywords
        or ["checkpoint", "review needed", "approval needed", "decision:"],
    }
    monkeypatch.setattr(
        gateway_run,
        "_load_gateway_config",
        lambda: {"kanban": {"checkpoint_notifications": cfg}},
    )
    runner = GatewayRunner.__new__(GatewayRunner)
    runner.config = GatewayConfig(
        platforms={
            Platform.DISCORD: PlatformConfig(
                enabled=True,
                home_channel=HomeChannel(
                    platform=Platform.DISCORD,
                    chat_id="1501780210578755715",
                    name="#hermes",
                ),
            )
        }
    )
    return runner


def _task(**overrides):
    data = dict(
        id="t_review",
        title="Decision: Gabriel approve Phase 1 visual direction",
        body="Review: /tmp/preview.png\nSafety: local-only/no-send",
        assignee="reviewer",
        status="blocked",
        priority=0,
        created_by="worker",
        created_at=1,
        started_at=None,
        completed_at=None,
        workspace_kind="scratch",
        workspace_path=None,
        claim_lock=None,
        claim_expires=None,
        tenant=None,
    )
    data.update(overrides)
    return kb.Task(**data)


def _event(kind="blocked", payload=None):
    return kb.Event(
        id=1,
        task_id="t_review",
        kind=kind,
        payload=payload if payload is not None else {"reason": "checkpoint reached: approve the preview"},
        created_at=2,
    )


def test_checkpoint_event_detection_matches_blocked_review_language(monkeypatch):
    runner = _runner(monkeypatch)

    assert runner._is_kanban_checkpoint_event(_task(), _event()) is True


def test_checkpoint_event_detection_matches_promoted_ready_checkpoint(monkeypatch):
    runner = _runner(monkeypatch)

    assert runner._is_kanban_checkpoint_event(
        _task(status="ready", title="Gabriel checkpoint: approve GHL Manager UI"),
        _event(kind="promoted", payload=None),
    ) is True


def test_checkpoint_event_detection_matches_gabriel_assignee_without_keyword(monkeypatch):
    runner = _runner(monkeypatch, keywords=["checkpoint"])

    assert runner._is_kanban_checkpoint_event(
        _task(assignee="gabriel", title="Approve launch"),
        _event(kind="promoted", payload=None),
    ) is True


def test_checkpoint_targets_prefer_board_specific_discord_channel(monkeypatch):
    runner = _runner(
        monkeypatch,
        checkpoint_config={
            "enabled": True,
            "default_target": "discord:1501780210578755715",
            "board_targets": {
                "ghl-manager-ui": "discord:1502593547122249758",
            },
        },
    )

    targets = runner._kanban_checkpoint_targets(Platform, board="ghl-manager-ui")

    assert len(targets) == 1
    assert targets[0]["platform"] is Platform.DISCORD
    assert targets[0]["chat_id"] == "1502593547122249758"
    assert targets[0]["name"] == "ghl-manager-ui"


def test_checkpoint_targets_fall_back_to_default_target_then_home(monkeypatch):
    runner = _runner(
        monkeypatch,
        checkpoint_config={
            "enabled": True,
            "default_target": "discord:1502593547122249758",
            "board_targets": {},
        },
    )

    configured = runner._kanban_checkpoint_targets(Platform, board="unknown-board")
    assert [t["chat_id"] for t in configured] == ["1502593547122249758"]

    runner = _runner(monkeypatch, checkpoint_config={"enabled": True, "platforms": ["discord"]})
    home = runner._kanban_checkpoint_targets(Platform, board="unknown-board")
    assert [t["chat_id"] for t in home] == ["1501780210578755715"]


def test_checkpoint_message_uses_standard_review_packet(monkeypatch):
    runner = _runner(monkeypatch)

    comments = [SimpleNamespace(body="What changed: Rebuilt Waterworx demo v2 as a premium local preview with desktop/mobile screenshots.")]
    runs = [SimpleNamespace(
        summary="Waterworx demo v2 redesign ready for review",
        metadata={
            "changed_files": ["/home/atlas/Projects/waterworx-demo-v2/index.html"],
            "tests_run": "playwright desktop/mobile smoke",
        },
    )]

    msg = runner._format_kanban_checkpoint_message(
        board="ghl-manager-ui",
        task=_task(body="""Artifact: /tmp/preview.png
How to view: xdg-open /tmp/preview.png
Safety: local-only/no-send
Acceptance criteria:
- Premium visual quality
- Mobile layout is usable
"""),
        event=_event(),
        comments=comments,
        runs=runs,
    )

    assert "## Gabriel review needed" in msg
    assert "**Project/task:** Decision: Gabriel approve Phase 1 visual direction" in msg
    assert "**Card:** ghl-manager-ui/t_review" in msg
    assert "**Assignee:** @reviewer" in msg
    assert "### What changed" in msg
    assert "- Summary: Waterworx demo v2 redesign ready for review" in msg
    assert "### Verification" in msg
    assert "- Tests/checks: playwright desktop/mobile smoke" in msg
    assert "- Acceptance/checklist: - Premium visual quality | - Mobile layout is usable" in msg
    assert "### Review needed" in msg
    assert "- Decision needed: checkpoint reached: approve the preview" in msg
    assert "### Links / artifacts" in msg
    assert "- Artifact: /tmp/preview.png" in msg
    assert "- How to view/run: xdg-open /tmp/preview.png" in msg
    assert "### Safety / next action" in msg
    assert "- Known risks/safety: local-only/no-send" in msg
    assert "- Reply options: `approve` / `needs changes: <what must change>`" in msg



def test_checkpoint_message_omits_bogus_artifact_from_prior_links_heading(monkeypatch):
    runner = _runner(monkeypatch)
    comments = [
        SimpleNamespace(body="""review-required handoff:
{
  "changed_files": ["gateway/run.py", "tests/gateway/test_kanban_checkpoint_notifications.py"],
  "tests_run": ["python -m pytest tests/gateway/test_kanban_checkpoint_notifications.py -q"],
  "summary": "Kanban review notifications are now sectioned with headings/bullets."
}

### Links / artifacts
- No explicit artifact for this code review."""),
        SimpleNamespace(body="""Gabriel review feedback from Discord:
> Gabriel review needed: Fix Kanban review notification formatting for scanability
> Artifact: / artifacts
> How to view/run: Local-only artifact: on Atlas, run `xdg-open '/ artifacts'`
"""),
    ]

    msg = runner._format_kanban_checkpoint_message(
        board="default",
        task=_task(
            id="t_5e5382e2",
            title="Fix Kanban review notification formatting for scanability",
            body="""Acceptance criteria:
- Update notifications so Discord packets use headings/sections and bullets.
- Preserve project/task, changed summary, verification/tests, artifacts/URLs, decision, and next action.
""",
        ),
        event=_event(payload={"reason": "review-required: needs human review before merge/restart"}),
        comments=comments,
    )

    assert msg.startswith("## Gabriel review needed\n")
    assert "Gabriel review needed:" not in msg
    assert "**Project/task:** Fix Kanban review notification formatting for scanability" in msg
    assert "### What changed" in msg
    assert "### Verification" in msg
    assert "### Review needed" in msg
    assert "### Links / artifacts" in msg
    assert "- No artifact/URL provided in the card or handoff comments" in msg
    assert "Artifact: / artifacts" not in msg
    assert "xdg-open '/ artifacts'" not in msg


def test_checkpoint_collection_advances_cursor_for_non_checkpoint_events(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    for key in ("HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD", "HERMES_KANBAN_WORKSPACES_ROOT"):
        monkeypatch.delenv(key, raising=False)

    kb.create_board("project-board", name="Project Board")
    kb.init_db(board="project-board")
    with kb.connect(board="project-board") as conn:
        parent = kb.create_task(conn, title="ordinary parent")
        kb.create_task(
            conn,
            title="Build ordinary implementation task",
            body="Implementation work with ordinary build details.",
            assignee="coder",
            parents=[parent],
        )
        kb.complete_task(conn, parent, summary="ready for implementation")

    runner = _runner(
        monkeypatch,
        checkpoint_config={
            "enabled": True,
            "default_target": "discord:1501780210578755715",
            "board_targets": {},
        },
    )

    collected = runner._collect_kanban_notifier_deliveries(Platform, kb)
    deliveries = [d for d in collected["checkpoints"] if d["board"] == "project-board"]

    assert len(deliveries) == 1
    assert deliveries[0]["items"] == []

    runner._kanban_checkpoint_advance(
        deliveries[0]["target_key"],
        deliveries[0]["cursor"],
        "project-board",
    )

    restarted = runner._collect_kanban_notifier_deliveries(Platform, kb)
    assert [d for d in restarted["checkpoints"] if d["board"] == "project-board"] == []


def test_checkpoint_message_formats_ghl_cards_as_operational_decisions(monkeypatch):
    runner = _runner(monkeypatch)

    msg = runner._format_kanban_checkpoint_message(
        board="ghl-six-priority-cleanup",
        task=_task(
            title="Approval: Vanessa weather update / Saturday safety decision",
            body="""Brand/location: Solar Renew
Contact: Vanessa / contact c_123 / +614****000
Job/service location: Suburb NSW
Latest customer ask/message: Asked whether the wet-weather Saturday job is still safe.
Last outbound/manual contact: We previously offered safer Saturday replacement slots.
Current state: Old appointment is still confirmed; replacement slots need live calendar and ledger recheck.
Why the action matters now: Weather/safety decision affects whether Gabriel attends today.
Recommended action: Ask Gabriel whether to proceed or reschedule; do not auto-send.
Exact draft text if choosing A: Hi Vanessa, with the weather looking unsafe I think best to move this one.
Send target/channel and brand/location: SMS via Solar Renew
Approval options: approve draft / reschedule manually / no action
""",
        ),
        event=_event(payload={"reason": "Blocked for Gabriel approval: weather/safety decision"}),
    )

    assert "## Blue/GHL approval needed" in msg
    assert "**Project/task:** Approval: Vanessa weather update / Saturday safety decision" in msg
    assert "- Customer: Vanessa / contact c_123 / +614****000" in msg
    assert "- Why now: Weather/safety decision affects whether Gabriel attends today." in msg
    assert "- Recommended next action: Ask Gabriel whether to proceed or reschedule; do not auto-send." in msg
    assert "- Draft/action: Hi Vanessa, with the weather looking unsafe I think best to move this one." in msg
    assert "**Card:** ghl-six-priority-cleanup/t_review" in msg
    assert "### Safety / next action" in msg
    assert "Artifact:" not in msg
    assert "How to view/run:" not in msg


def test_checkpoint_message_prefers_explicit_artifact_label_over_project_path(monkeypatch):
    runner = _runner(monkeypatch)

    msg = runner._format_kanban_checkpoint_message(
        board="mission-control",
        task=_task(body="""Project path: /home/atlas/Projects/hermes-mission-control
Artifact: /tmp/preview.png
Safety: local-only/no-send
"""),
        event=_event(),
    )

    assert "Artifact: /tmp/preview.png" in msg
    assert "Artifact: /home/atlas/Projects/hermes-mission-control" not in msg


def test_checkpoint_message_handles_string_changed_files_in_json_comment(monkeypatch):
    runner = _runner(monkeypatch)
    comments = [SimpleNamespace(body='review-required handoff:\n{"summary":"Preview ready","changed_files":"/tmp/preview.png"}')]

    msg = runner._format_kanban_checkpoint_message(
        board="mission-control",
        task=_task(),
        event=_event(),
        comments=comments,
    )

    assert "Changed/artifacts: /tmp/preview.png" in msg
    assert "Changed/artifacts: /, t, m" not in msg

def test_checkpoint_collection_routes_promoted_once_to_board_target(monkeypatch, tmp_path):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("HERMES_KANBAN_HOME", str(home))
    for key in ("HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD", "HERMES_KANBAN_WORKSPACES_ROOT"):
        monkeypatch.delenv(key, raising=False)

    kb.create_board("ghl-manager-ui", name="GHL Manager UI")
    kb.init_db(board="ghl-manager-ui")
    with kb.connect(board="ghl-manager-ui") as conn:
        parent = kb.create_task(conn, title="review parent")
        checkpoint = kb.create_task(
            conn,
            title="Gabriel checkpoint: approve GHL Manager UI",
            body="Review: /tmp/preview.png\nSafety: local-only/no-send",
            assignee="gabriel",
            parents=[parent],
        )
        kb.complete_task(conn, parent, summary="ready for Gabriel checkpoint")

    runner = _runner(
        monkeypatch,
        checkpoint_config={
            "enabled": True,
            "default_target": "discord:#inbox",
            "board_targets": {"ghl-manager-ui": "discord:1502593547122249758"},
        },
    )

    collected = runner._collect_kanban_notifier_deliveries(Platform, kb)
    deliveries = [d for d in collected["checkpoints"] if d["board"] == "ghl-manager-ui"]

    assert len(deliveries) == 1
    assert deliveries[0]["target"]["chat_id"] == "1502593547122249758"
    assert deliveries[0]["items"][0]["event"].kind == "promoted"
    assert deliveries[0]["items"][0]["event"].task_id == checkpoint
    assert "comments" in deliveries[0]["items"][0]
    assert "runs" in deliveries[0]["items"][0]

    runner._kanban_checkpoint_advance(
        deliveries[0]["target_key"],
        deliveries[0]["cursor"],
        "ghl-manager-ui",
    )

    restarted = runner._collect_kanban_notifier_deliveries(Platform, kb)
    assert [d for d in restarted["checkpoints"] if d["board"] == "ghl-manager-ui"] == []
