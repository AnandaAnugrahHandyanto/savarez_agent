# feat(plugins): expose Slack AsyncApp init hook

## Motivation

Hermes can register first-party Slack Block Kit handlers, but external plugins
do not have a stable Slack adapter lifecycle point for registering
`app.command`, `app.action`, `app.view`, or `app.event` callbacks.

This PR adds a plugin-agnostic `on_slack_app_init` hook so Block Kit features
can live in plugins instead of being hardcoded into `gateway/platforms/slack.py`.
Expected uses include meeting-room UI, kanban boards, custom slash commands,
and approval workflow extensions.

## API

Plugins register the hook through the existing plugin API:

```python
def on_slack_app_init(*, app, adapter, profile, web_clients, bot_user_id):
    @app.command("/meeting")
    async def meeting(ack, command):
        await ack()
```

The hook receives:

- `app`: the Slack Bolt `AsyncApp`
- `adapter`: the active `SlackAdapter`
- `profile`: profile name when available
- `web_clients`: team id to `AsyncWebClient` mapping
- `bot_user_id`: primary bot user id

## Behavior

The hook fires after core Slack event handlers are registered and before the
native slash fallback matcher. This lets plugin-owned slash handlers take Bolt
priority over the generic native command matcher.

If hook invocation itself fails, Slack startup aborts and `connect()` returns
`False`, matching the adapter's existing startup-failure behavior.

## Backward Compatibility

- Adds one `VALID_HOOKS` entry.
- No behavior change when no plugin registers the hook.
- No plugin-specific code is added to the Slack adapter.

## Tests

- `tests/cli/test_plugins_valid_hooks.py`
- `tests/gateway/platforms/test_slack_on_app_init_hook.py`
- `tests/gateway/platforms/test_slack_plugin_slash_priority.py`
