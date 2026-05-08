import pytest

from agent.skill_nudge_signals import SignalEvaluator


@pytest.fixture
def ev():
    return SignalEvaluator(
        repeated_threshold=3,
        error_threshold=2,
        common_clis_suppressed=["git", "ls"],
        cli_window_days=30,
        user_phrases=["next time", "记一下"],
    )


def test_s1_repeated_terminal_first_token(ev):
    for _ in range(3):
        ev.observe_tool_call("terminal", {"command": "gh pr view 123"})

    assert "S1" in ev.fired_signals


def test_s1_unknown_tool_does_not_fire(ev):
    for _ in range(5):
        ev.observe_tool_call("custom_tool", {"foo": "bar"})

    assert "S1" not in ev.fired_signals


def test_s2_novel_cli_fires(ev, monkeypatch):
    monkeypatch.setattr("agent.skill_usage_tracker.is_known_cli", lambda *a, **kw: False)
    monkeypatch.setattr("agent.skill_usage_tracker.record_cli_seen", lambda *a, **kw: None)

    ev.observe_tool_call("terminal", {"command": "exotic-cli --do-thing"}, success=True)

    assert "S2" in ev.fired_signals


def test_s2_common_cli_suppressed(ev, monkeypatch):
    monkeypatch.setattr("agent.skill_usage_tracker.is_known_cli", lambda *a, **kw: False)
    monkeypatch.setattr("agent.skill_usage_tracker.record_cli_seen", lambda *a, **kw: None)

    ev.observe_tool_call("terminal", {"command": "git status"}, success=True)

    assert "S2" not in ev.fired_signals


def test_s3_user_phrase_match(ev):
    ev.observe_user_message("This always crashes, please remember next time")

    assert "S3" in ev.fired_signals


def test_s4_resolved_repeated_error(ev):
    ev.observe_tool_result("terminal", error_text="ENOENT: file 'x' not found")
    ev.observe_tool_result("terminal", error_text="ENOENT: file 'x' not found")
    ev.observe_tool_result("terminal", error_text=None)

    assert "S4" in ev.fired_signals


def test_clear_resets_state(ev):
    for _ in range(3):
        ev.observe_tool_call("terminal", {"command": "gh pr view"})

    assert ev.fired_signals
    ev.clear()
    assert not ev.fired_signals
