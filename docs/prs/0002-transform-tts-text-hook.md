# feat(gateway): add transform_tts_text plugin hook

## Motivation

Gateway voice replies synthesize the final assistant text directly. Plugins
that add machine-readable metadata to normal chat text need a supported way to
strip or rewrite that text before TTS synthesis without changing the visible
Slack message.

This PR adds `transform_tts_text`, a voice-surface counterpart to the existing
terminal and LLM transform hooks.

## API

Plugins register a sync callback through the existing plugin hook API:

```python
def transform_tts_text(*, text, event):
    return text.replace("[MEETING]", "")
```

The hook receives:

- `text`: the assistant text selected for voice synthesis
- `event`: the originating `MessageEvent`

Return a string to replace the synthesis text. Return `None` to leave the text
unchanged.

## Behavior

Hermes currently exposes sync `invoke_hook()` semantics, not a true async chain
helper. The gateway therefore invokes all callbacks once with the original
`text` and uses the last non-`None` string return value as the text to
synthesize.

This is intentionally documented as last-writer-wins rather than true chain
semantics. A future helper could provide chain semantics without changing the
hook name.

Hook invocation is fail-soft in the TTS path. If invocation raises, the gateway
logs the failure and synthesizes the original text.

## Backward Compatibility

- Adds one `VALID_HOOKS` entry.
- No behavior change when no plugin registers the hook.
- Existing markdown stripping still runs after this transform.

## Tests

- `tests/cli/test_plugins_valid_hooks.py`
- `tests/gateway/test_run_tts_transform_hook.py`
