from pathlib import Path

from agent.failure_registry import record_failure


def test_record_failure_writes_structured_markdown(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / ".hermes"))

    path = record_failure(
        trigger="spar_rejection",
        symptom="builder returned the wrong payload",
        root_cause="reviewer found a missing required field",
        fix="return the requested field",
        prevention="run spar before shipping",
        related_skills=["spar", "ratchet"],
        session_id="session-123",
        metadata={"model": "xiaomi/mimo-v2-pro"},
    )

    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert "## Trigger" in text
    assert "spar_rejection" in text
    assert "session-123" in text
    assert "xiaomi/mimo-v2-pro" in text
