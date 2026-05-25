# refactor(slack): allow plugin slash handlers to take Bolt priority

## Motivation

The Slack adapter registers a single regex matcher for native Hermes slash
commands. Plugin-owned Block Kit flows often need to handle a slash command
directly in Bolt so they can open modals, post ephemeral panels, and own their
callback state.

Rather than adding a plugin command flag or Slack-specific command metadata,
this PR moves `on_slack_app_init` before the native slash fallback matcher.
Plugins that register `app.command("/name")` in that hook are matched first by
Bolt registration order.

## Behavior

Registration order after this PR:

1. Core Slack event handlers.
2. `on_slack_app_init` plugin hook.
3. Native Hermes slash fallback matcher.
4. Core approval and confirmation action handlers.
5. Socket Mode startup.

This keeps plugin commands explicit and avoids adding new command-registry API
surface area.

## Backward Compatibility

- No new public command flags.
- Native Hermes slash commands still use the same regex fallback.
- Plugins that do not register Slack commands are unaffected.

## Tests

- `tests/gateway/platforms/test_slack_plugin_slash_priority.py`
- `tests/gateway/platforms/test_slack_on_app_init_hook.py`
