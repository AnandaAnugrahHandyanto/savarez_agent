import asyncio
import re
from unittest.mock import patch


async def _dispatch_slash(app, *, command="/meeting", text="topic"):
    payload = {
        "command": command,
        "text": text,
        "channel_id": "C_FAKE",
        "user_id": "U_FAKE",
        "team_id": "T_FAKE",
    }

    async def ack(*args, **kwargs):
        return None

    for matcher, handler in app.registered_commands:
        if isinstance(matcher, str):
            matched = matcher == command
        elif isinstance(matcher, re.Pattern):
            matched = bool(matcher.match(command))
        else:
            matched = False
        if matched:
            await handler(ack, payload)
            return

    raise AssertionError(f"No registered slash handler matched {command}")


def test_plugin_registered_slash_takes_priority_over_native_batched_handler(
    slack_adapter_factory,
):
    """A plugin app.command registered from the init hook wins by Bolt order."""
    plugin_invocations = []
    native_invocations = []

    def hook(name, *, app, **kwargs):
        assert name == "on_slack_app_init"

        @app.command("/meeting")
        async def plugin_meeting_handler(ack, command):
            plugin_invocations.append(command)
            await ack()

        return []

    async def native_handler(command):
        native_invocations.append(command)

    adapter = slack_adapter_factory()
    adapter._handle_slash_command = native_handler

    with patch("hermes_cli.plugins.invoke_hook", side_effect=hook):
        with patch(
            "hermes_cli.commands.slack_native_slashes",
            return_value=[("meeting", "Meeting fallback", "")],
        ):
            assert asyncio.run(adapter.connect()) is True

    asyncio.run(_dispatch_slash(adapter._app, command="/meeting", text="topic"))

    assert len(plugin_invocations) == 1
    assert plugin_invocations[0]["text"] == "topic"
    assert native_invocations == []
