import json

from hermes_cli.warp_notifications import (
    OSC_PREFIX,
    OSC_SUFFIX,
    WarpAgentNotifier,
    _safe_text,
    configured_mode,
    should_enable,
    warp_protocol_available,
)


def test_warp_protocol_detection_requires_warp_and_protocol():
    assert warp_protocol_available(
        {
            "TERM_PROGRAM": "WarpTerminal",
            "WARP_CLI_AGENT_PROTOCOL_VERSION": "1",
        }
    )
    assert not warp_protocol_available({"TERM_PROGRAM": "WarpTerminal"})
    assert not warp_protocol_available(
        {
            "TERM_PROGRAM": "Apple_Terminal",
            "WARP_CLI_AGENT_PROTOCOL_VERSION": "1",
        }
    )


def test_config_mode_supports_env_override():
    config = {"display": {"warp_notifications": "off"}}
    assert configured_mode(config, {"HERMES_WARP_NOTIFICATIONS": "on"}) == "on"
    assert configured_mode({"display": {"warp_notifications": True}}, {}) == "on"
    assert configured_mode({"display": {"warp_notifications": False}}, {}) == "off"
    assert configured_mode({}, {}) == "auto"


def test_auto_enable_only_when_warp_protocol_is_available():
    config = {"display": {"warp_notifications": "auto"}}
    assert should_enable(
        config,
        {
            "TERM_PROGRAM": "WarpTerminal",
            "WARP_CLI_AGENT_PROTOCOL_VERSION": "1",
        },
    )
    assert not should_enable(config, {"TERM_PROGRAM": "WarpTerminal"})
    assert should_enable({"display": {"warp_notifications": "on"}}, {})
    assert not should_enable({"display": {"warp_notifications": "off"}}, {})


def test_safe_text_redacts_prefixed_env_style_secrets():
    text = _safe_text(
        "OPENAI_API_KEY=sk-test ANTHROPIC_API_KEY=sk-ant "
        "GITHUB_TOKEN=ghp_secret AWS_SECRET_ACCESS_KEY=awssecret "
        "Authorization: Bearer bearersecret"
    )

    assert "sk-test" not in text
    assert "sk-ant" not in text
    assert "ghp_secret" not in text
    assert "awssecret" not in text
    assert "bearersecret" not in text
    assert "OPENAI_API_KEY=[REDACTED]" in text


def test_emit_writes_structured_cli_agent_osc_to_writer():
    writes = []
    notifier = WarpAgentNotifier(
        enabled=True,
        session_id="session-1",
        cwd="/tmp/hermes-project",
        writer=writes.append,
    )

    assert notifier.emit(
        "permission_request",
        summary="Approval requested: OPENAI_API_KEY=sk-test123 and GITHUB_TOKEN=ghp_secret123",
        tool_name="terminal",
        tool_input={"command": "curl -H 'Authorization: Bearer secret' https://example.test"},
    )

    assert len(writes) == 1
    data = writes[0]
    assert data.startswith(OSC_PREFIX)
    assert data.endswith(OSC_SUFFIX)
    payload = json.loads(data[len(OSC_PREFIX) : -len(OSC_SUFFIX)])
    assert payload["v"] == 1
    assert payload["agent"] == "hermes"
    assert payload["event"] == "permission_request"
    assert payload["session_id"] == "session-1"
    assert payload["cwd"] == "/tmp/hermes-project"
    assert payload["project"] == "hermes-project"
    assert payload["tool_name"] == "terminal"
    assert "sk-test123" not in payload["summary"]
    assert "ghp_secret123" not in payload["summary"]
    assert "secret" not in payload["tool_input"]["command"]


def test_disabled_notifier_does_not_write():
    writes = []
    notifier = WarpAgentNotifier(
        enabled=False,
        session_id="session-1",
        writer=writes.append,
    )

    assert notifier.emit("stop", summary="Done") is False
    assert writes == []


def test_cli_warp_lifecycle_sets_and_clears_pending_stop():
    from cli import HermesCLI

    class FakeNotifier:
        enabled = True
        project = None
        cwd = None
        session_id = None

        def __init__(self):
            self.events = []

        def emit(self, event, **fields):
            self.events.append((event, fields))
            return True

    fake = FakeNotifier()
    cli = object.__new__(HermesCLI)
    cli.session_id = "session-1"
    cli._warp_notifier = fake
    cli._warp_session_started = False
    cli._warp_turn_needs_stop = False

    cli._warp_notify_prompt_submit()
    assert [event for event, _ in fake.events] == ["session_start", "prompt_submit"]
    assert cli._warp_session_started is True
    assert cli._warp_turn_needs_stop is True

    cli._warp_notify_stop(failed=True)
    assert fake.events[-1][0] == "stop"
    assert fake.events[-1][1]["summary"] == "Hermes stopped with an error"
    assert cli._warp_turn_needs_stop is False
