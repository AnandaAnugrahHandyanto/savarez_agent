import json
from types import SimpleNamespace

from agent import initiative_engine as engine


NOW = 1779536000.0


def _source():
    return SimpleNamespace(platform=SimpleNamespace(value="telegram"))


def _history(ts=NOW):
    return [{"role": "user", "content": "go", "timestamp": ts}]


def _write_persona(tmp_path, *, ne_pas_deranger=0.2, timestamp=NOW):
    (tmp_path / "inner_state.json").write_text(
        json.dumps(
            {
                "timestamp": timestamp,
                "attention_targets": ["spec", "kanban", "runtime"],
                "dominant_thought": "ranger les specs et suivre le kanban",
                "current_obsessions": ["initiative deterministe"],
            }
        )
    )
    (tmp_path / "desires.json").write_text(
        json.dumps([{"name": "ne_pas_deranger", "weight": ne_pas_deranger}])
    )


def test_archives_detected_spec_and_logs_decision(tmp_path):
    _write_persona(tmp_path)
    docs = tmp_path / "documents" / "specs"
    response = """# Spec : Proactivite test

**Statut** : spec

## Vision

Judy range ce document.
"""

    results = engine.maybe_take_initiative(
        response=response,
        history=_history(),
        source=_source(),
        session_key="telegram:1",
        persona_root=tmp_path,
        spec_archive_root=docs,
        now=NOW,
    )

    assert len(results) == 1
    assert results[0].executed is True
    assert results[0].decision.opportunity.action_type == "archive_spec"
    archived = docs / "proactivite-test.md"
    assert archived.exists()
    assert archived.read_text().startswith("# Spec : Proactivite test")
    assert "## Vision" in archived.read_text()

    log_rows = [
        json.loads(line)
        for line in (tmp_path / "initiative_log.jsonl").read_text().splitlines()
    ]
    assert log_rows[-1]["schema_version"] == 1
    assert log_rows[-1]["decision"]["decision"] == "act"


def test_recent_duplicate_is_skipped(tmp_path):
    _write_persona(tmp_path)
    docs = tmp_path / "documents" / "specs"
    response = """# Spec : Doublon

**Statut** : spec

## Vision

Contenu.
"""

    first = engine.maybe_take_initiative(
        response=response,
        history=_history(),
        persona_root=tmp_path,
        spec_archive_root=docs,
        now=NOW,
    )
    second = engine.maybe_take_initiative(
        response=response,
        history=_history(),
        persona_root=tmp_path,
        spec_archive_root=docs,
        now=NOW + 60,
    )

    assert first[0].executed is True
    assert second[0].executed is False
    assert second[0].decision.reason == "duplicate_recent"


def test_level_three_defers_during_active_conversation_then_runs_on_inactivity(tmp_path, monkeypatch):
    _write_persona(tmp_path)
    calls = []

    def fake_execute(decision, **kwargs):
        calls.append((decision.opportunity.action_type, kwargs))
        return {"status": "commented"}

    monkeypatch.setattr(engine, "execute_action", fake_execute)
    response = "Le ticket ABC-123 est debloque et mérite un commentaire de suivi."

    active = engine.maybe_take_initiative(
        response=response,
        history=_history(),
        persona_root=tmp_path,
        now=NOW,
    )

    assert active[0].decision.opportunity.level == 3
    assert active[0].decision.decision == "defer"
    assert active[0].decision.reason == "conversation_active"
    assert calls == []

    (tmp_path / "last_user_activity.json").write_text(
        json.dumps({"timestamp": NOW - 600})
    )
    inactive = engine.maybe_take_initiative(
        trigger="inactivity",
        history=[],
        persona_root=tmp_path,
        now=NOW + 600,
    )

    assert inactive[0].executed is True
    assert calls[0][0] == "kanban_comment"
    pending = json.loads((tmp_path / "pending_actions.json").read_text())
    assert pending["actions"] == []


def test_do_not_disturb_blocks_level_three_execution(tmp_path, monkeypatch):
    _write_persona(tmp_path, ne_pas_deranger=0.9)
    monkeypatch.setattr(
        engine,
        "execute_action",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("no execution")),
    )
    (tmp_path / "last_user_activity.json").write_text(
        json.dumps({"timestamp": NOW - 600})
    )
    pending = {
        "schema_version": 1,
        "actions": [
            {
                "fingerprint": "kanban_comment:x",
                "status": "defer",
                "opportunity": {
                    "kind": "kanban",
                    "action_type": "kanban_comment",
                    "level": 3,
                    "title": "Comment kanban task ABC-123",
                    "content": "Commentaire",
                    "target": "ABC-123",
                    "metadata": {},
                },
            }
        ],
        "seen": [],
    }
    (tmp_path / "pending_actions.json").write_text(json.dumps(pending))

    results = engine.maybe_take_initiative(
        trigger="inactivity",
        history=[],
        persona_root=tmp_path,
        now=NOW,
    )

    assert results[0].decision.decision == "defer"
    assert results[0].decision.reason == "do_not_disturb_level_gate"


def test_do_not_disturb_prefers_migrated_desire_traits(tmp_path, monkeypatch):
    _write_persona(tmp_path, ne_pas_deranger=0.1)
    (tmp_path / "desire_traits.json").write_text(
        json.dumps({"schema_version": 1, "traits": [{"name": "ne_pas_deranger", "weight": 0.9}]})
    )
    monkeypatch.setattr(
        engine,
        "execute_action",
        lambda *_, **__: (_ for _ in ()).throw(AssertionError("no execution")),
    )
    (tmp_path / "last_user_activity.json").write_text(
        json.dumps({"timestamp": NOW - 600})
    )
    pending = {
        "schema_version": 1,
        "actions": [
            {
                "fingerprint": "kanban_comment:x",
                "status": "defer",
                "opportunity": {
                    "kind": "kanban",
                    "action_type": "kanban_comment",
                    "level": 3,
                    "title": "Comment kanban task ABC-123",
                    "content": "Commentaire",
                    "target": "ABC-123",
                    "metadata": {},
                },
            }
        ],
        "seen": [],
    }
    (tmp_path / "pending_actions.json").write_text(json.dumps(pending))

    results = engine.maybe_take_initiative(
        trigger="inactivity",
        history=[],
        persona_root=tmp_path,
        now=NOW,
    )

    assert results[0].decision.reason == "do_not_disturb_level_gate"


def test_level_five_requires_approval_even_with_high_score(tmp_path):
    _write_persona(tmp_path)

    results = engine.maybe_take_initiative(
        response="ALERTE critique: corruption detectee dans state.json.",
        history=[],
        persona_root=tmp_path,
        now=NOW,
    )

    assert results[0].decision.opportunity.level == 5
    assert results[0].decision.decision == "requires_approval"
    assert results[0].decision.reason == "level_not_enabled"


def test_malformed_pending_file_is_recovered(tmp_path):
    _write_persona(tmp_path)
    (tmp_path / "pending_actions.json").write_text("not json")

    results = engine.maybe_take_initiative(
        trigger="inactivity",
        history=[],
        persona_root=tmp_path,
        now=NOW,
    )

    assert results == []
    pending = json.loads((tmp_path / "pending_actions.json").read_text())
    assert pending["actions"] == []


def test_active_conversation_lowers_interference_dimension():
    opportunity = engine.Opportunity(
        kind="kanban",
        action_type="kanban_comment",
        level=3,
        title="Comment kanban task ABC-123",
    )

    active_dims, active_base, _ = engine.score_opportunity(
        opportunity,
        inner_state={"attention_targets": ["kanban"]},
        active_conversation=True,
    )
    idle_dims, idle_base, _ = engine.score_opportunity(
        opportunity,
        inner_state={"attention_targets": ["kanban"]},
        active_conversation=False,
    )

    assert active_dims["interference"] < idle_dims["interference"]
    assert active_base < idle_base
