# Fix: Custom fallback providers fail silently when they don't support SSE streaming

**Issue:** #21522

## Problem

When a custom fallback provider returns a non-streaming JSON response to a `stream=True` request:
1. The OpenAI SDK's streaming parser receives zero chunks
2. `content_parts` stays empty → `full_content = None`
3. Response flagged as "empty" → retry loop → fallback cascade
4. Valid response silently discarded

The existing `_disable_streaming` flag is session-wide and only triggers *after* the provider explicitly rejects streaming with a "stream not supported" error message. Providers that silently return JSON instead of SSE are not detected.

## Root Cause

Two independent gaps:

1. **No per-provider streaming config:** `fallback_providers` entries accept `provider`, `model`, `base_url`, `api_key`, `key_env` — but no `stream` flag. Users can't say "this provider doesn't support streaming."

2. **No detection of non-SSE JSON responses in streaming path:** When `stream=True` is sent but the server returns `Content-Type: application/json` instead of `text/event-stream`, the SDK yields zero chunks. This is distinguishable from a genuine empty response.

## Solution (Option A+B from the issue)

### Part 1: Per-provider `stream` config flag

Add a `stream` boolean to fallback provider config:

```yaml
fallback_providers:
  - provider: custom
    model: my-model
    base_url: http://my-proxy:8080/v1
    stream: false
```

When `stream: false` is set, `_disable_streaming` is applied specifically for that provider. When falling back away from that provider, streaming state is restored.

### Part 2: Auto-detect non-SSE responses in streaming path

After the streaming loop completes, if `content_parts` is empty AND `tool_calls_acc` is empty AND the stream yielded zero chunks, attempt a non-streaming retry before declaring the response empty.

### Implementation Steps

1. **`run_agent.py` — `_try_activate_fallback()`:** Read `fb.get("stream", True)` and set/clear `_disable_streaming` accordingly. Save previous streaming state to restore on next fallback.

2. **`run_agent.py` — `_interruptible_streaming_api_call()` → `_call_chat_completions()`:** After the streaming loop, detect zero-chunk responses. If the stream produced no chunks at all (not even an empty-choices keepalive), set `_disable_streaming = True` and raise a retriable error so the main loop retries with non-streaming.

3. **`hermes_cli/config.py`:** Document `stream` as a valid fallback provider field.

4. **`cli-config.yaml.example`:** Add example showing `stream: false` usage.

5. **Tests:** 
   - Test per-provider `stream: false` config sets `_disable_streaming`
   - Test streaming state restoration when advancing fallback chain
   - Test zero-chunk detection triggers non-streaming retry

## Files Changed

| File | Change |
|------|--------|
| `run_agent.py` | Per-provider streaming flag in `_try_activate_fallback()`, zero-chunk detection in streaming path |
| `hermes_cli/config.py` | Document `stream` field in fallback provider validation |
| `cli-config.yaml.example` | Add fallback provider streaming example |
| `tests/run_agent/test_fallback_streaming.py` | New test file for streaming fallback behavior |
