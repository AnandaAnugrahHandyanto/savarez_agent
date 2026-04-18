import json
from pathlib import Path

from agent.compaction_checkpoint import write_compaction_checkpoint


def _sample_messages():
    return [
        {"role": "user", "content": "Build the Thindi SEO architecture plan."},
        {"role": "assistant", "content": "I gathered the current constraints and architecture options."},
        {"role": "tool", "content": "{\"status\": \"success\", \"output\": \"Council review loaded\"}"},
        {"role": "user", "content": "Continue from the council review and produce final blind spots."},
        {"role": "assistant", "content": "Working through the final synthesis now."},
    ]


def test_write_compaction_checkpoint_creates_canonical_artifacts(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes" / "profiles" / "thindi"
    workspace = hermes_home / "workspace"
    workspace.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    result = write_compaction_checkpoint(
        session_id="session-123",
        messages=_sample_messages(),
        preservation_notes="Preserve exact port 8642 and the unresolved backlink strategy gap.",
        approx_tokens=185000,
        context_length=200000,
        threshold_tokens=185000,
    )

    handoff_path = Path(result["handoff_path"])
    checkpoint_json_path = Path(result["checkpoint_json_path"])
    event_path = Path(result["event_path"])
    daily_path = Path(result["daily_path"])
    latest_path = Path(result["latest_handoff_path"])

    assert handoff_path.exists()
    assert checkpoint_json_path.exists()
    assert event_path.exists()
    assert daily_path.exists()
    assert latest_path.exists()

    checkpoint_payload = json.loads(checkpoint_json_path.read_text())
    assert checkpoint_payload["session_id"] == "session-123"
    assert checkpoint_payload["profile"] == "thindi"
    assert checkpoint_payload["fleet"] == "generic"
    assert checkpoint_payload["context_length"] == 200000
    assert checkpoint_payload["threshold_tokens"] == 185000
    assert checkpoint_payload["context_percent"] == 92.5
    assert "8642" in checkpoint_payload["preservation_notes"]

    event_lines = [line for line in event_path.read_text().splitlines() if line.strip()]
    assert len(event_lines) == 1
    event_payload = json.loads(event_lines[0])
    assert event_payload["kind"] == "compaction_checkpoint"
    assert event_payload["session_id"] == "session-123"
    assert event_payload["profile"] == "thindi"

    daily_text = daily_path.read_text()
    assert "Compaction Checkpoint" in daily_text
    assert "session-123" in daily_text
    assert "185000" in daily_text

    latest_text = latest_path.read_text()
    assert "session-123" in latest_text


def test_write_compaction_checkpoint_appends_event_jsonl(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes"
    workspace = hermes_home / "workspace"
    workspace.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    write_compaction_checkpoint(
        session_id="session-a",
        messages=_sample_messages(),
        preservation_notes="first",
        approx_tokens=90000,
        context_length=100000,
        threshold_tokens=85000,
    )
    second = write_compaction_checkpoint(
        session_id="session-b",
        messages=_sample_messages(),
        preservation_notes="second",
        approx_tokens=91000,
        context_length=100000,
        threshold_tokens=85000,
    )

    event_path = Path(second["event_path"])
    lines = [json.loads(line) for line in event_path.read_text().splitlines() if line.strip()]
    assert [line["session_id"] for line in lines] == ["session-a", "session-b"]


def test_write_compaction_checkpoint_prefers_existing_legacy_book_memory_root(tmp_path, monkeypatch):
    hermes_home = tmp_path / ".hermes" / "profiles" / "generic-core"
    legacy_memory_root = hermes_home / "workspace" / "pantheon-migrated" / "workspace-generic" / "memory"
    legacy_memory_root.mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    result = write_compaction_checkpoint(
        session_id="legacy-session",
        messages=_sample_messages(),
        preservation_notes="legacy",
        approx_tokens=120000,
        context_length=200000,
        threshold_tokens=185000,
    )

    assert str(legacy_memory_root) in result["handoff_path"]
    assert str(legacy_memory_root) in result["event_path"]
