from agent.cmh_subprocess.budget_display import format_budget_status
from agent.cmh_subprocess.envelope import default_envelope_state
from agent.cmh_subprocess.halt_flags import default_halt_flags


def test_budget_status_formats_default_state_without_secrets():
    output = format_budget_status(default_envelope_state(), default_halt_flags())

    assert "Cowork envelope: 0/191 used, 191 available, window not started" in output
    assert "Codex envelope: 0/170 used, 170 available, window not started" in output
    assert "Halt flags: all=false, cowork_headless=false, codex_auto_dispatch=false" in output
    assert "API_KEY" not in output
    assert "TOKEN" not in output
    assert "SECRET" not in output


def test_budget_status_formats_used_counts_and_window():
    state = default_envelope_state()
    state["anthropic_max"]["envelope_messages_used_5h"] = 5
    state["anthropic_max"]["window_start_iso"] = "2026-05-17T20:00:00+00:00"
    flags = default_halt_flags()
    flags["cowork_headless"] = True

    output = format_budget_status(state, flags)

    assert "Cowork envelope: 5/191 used, 186 available, window started 2026-05-17T20:00:00+00:00" in output
    assert "cowork_headless=true" in output
