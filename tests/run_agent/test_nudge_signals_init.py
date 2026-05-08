def test_nudge_state_initialized_with_defaults(monkeypatch):
    from run_agent import AIAgent

    a = AIAgent.__new__(AIAgent)
    AIAgent._init_nudge_state(a, {})

    assert a._nudge_disabled is False
    assert a._nudge_signals == set()
    assert a._nudge_signals_enabled is False
    assert a._nudge_repeated_threshold == 3
    assert a._nudge_error_threshold == 2
    assert a._nudge_cli_window_days == 30
    assert a._nudge_user_phrases == ["next time", "remember", "from now on", "记一下", "下次", "以后"]
    assert "git" in a._nudge_common_clis_suppressed


def test_nudge_state_reads_config():
    from run_agent import AIAgent

    cfg = {
        "skills": {
            "nudge_signals": {
                "enabled": True,
                "repeated_pattern_threshold": 5,
                "error_repeat_threshold": 3,
                "novel_cli_window_days": 14,
                "common_cli_suppressions": ["bun"],
                "user_phrases": ["foo"],
            }
        }
    }
    a = AIAgent.__new__(AIAgent)
    AIAgent._init_nudge_state(a, cfg)

    assert a._nudge_signals_enabled is True
    assert a._nudge_repeated_threshold == 5
    assert a._nudge_error_threshold == 3
    assert a._nudge_cli_window_days == 14
    assert a._nudge_common_clis_suppressed == ["bun"]
    assert a._nudge_user_phrases == ["foo"]


def test_nudge_env_var_disables_at_init(monkeypatch):
    from run_agent import AIAgent

    monkeypatch.setenv("HERMES_SKILL_NUDGE_DISABLE", "1")
    a = AIAgent.__new__(AIAgent)
    AIAgent._init_nudge_state(a, {"skills": {"nudge_signals": {"enabled": True}}})

    assert a._nudge_disabled is True
