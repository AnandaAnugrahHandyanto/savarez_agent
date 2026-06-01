# SimpleX Native Voice Handoff

Date: 2026-05-31

This handoff captures the current state of the SimpleX native voice work for Hermes Agent on Bryan's Mac, the verification already performed, and the next implementation steps. It is written so another agent can continue without relying on the prior chat transcript.

## Goal

Make SimpleX the verified native voice interface for Hermes Agent on this Mac. Authorized inbound SimpleX calls from Bryan's iPhone should be answered through the native SimpleX/WebRTC call path, stay connected, decode inbound audio, run local STT, execute a Hermes agent turn, synthesize local TTS, and stream the response back into the same SimpleX call.

The goal also requires redacted tracing, simulated call debugging, automated tests, and one successful manual iPhone spoken round trip.

## Current User Feedback

Bryan confirmed that he heard Hermes speak during a live SimpleX call. He asked a weather question. Hermes responded, but:

- STT misheard part of the request.
- Weather handling was not good enough because the call agent did not coalesce the weather request into an actual weather/tool lookup.
- Interruption/barge-in logic was poor.
- Bryan expects the debugging loop to be observable from logs/traces without requiring him to describe every failure in chat.

This feedback is the current product direction: keep improving observability, weather/tool routing, STT accuracy, and interruption behavior.

## Machine/Profile State

Repo:

```text
/Users/bryanmurphy/PROJECTS/Hermes-Agent
```

Active Hermes profile for this work:

```text
/Users/bryanmurphy/.hermes/profiles/bryan-main
```

Gateway launchd service:

```text
gui/501/ai.hermes.gateway-bryan-main
```

The gateway is started with:

```text
/Users/bryanmurphy/PROJECTS/Hermes-Agent/.venv/bin/python -m hermes_cli.main --profile bryan-main gateway run --replace
```

Important profile config:

```yaml
calls:
  browser:
    base_url: https://bryans-mac-mini.tail670355.ts.net/call
    public_exposure_enabled: false
    ttl_seconds: 600
    media_bridge:
      enabled: true
      status_url: http://127.0.0.1:18789/health
      worker_status_command:
      - launchctl
      - print
      - gui/501/ai.hermes.call-worker-bryan-main
  native:
    debug:
      transcript_previews: true
      max_preview_chars: 240
    agent:
      provider: copilot
      model: gpt-4o-mini
      base_url: https://api.githubcopilot.com
      api_mode: chat_completions
      max_iterations: 2
      max_tokens: 256
      enabled_toolsets: []
      disabled_toolsets:
      - terminal
      skip_context_files: true
      skip_memory: true
      system_prompt: Keep replies short and natural for a live phone call.
```

Voice provider health currently reports:

```json
{
  "ok": true,
  "stt": {
    "requested_provider": "local",
    "provider": "local_command",
    "local": true,
    "available": true,
    "error": ""
  },
  "tts": {
    "provider": "piper",
    "local": true,
    "available": true,
    "error": ""
  }
}
```

## Current Implementation State

### Native SimpleX/WebRTC Call Path

The native path now exists and has been exercised live and in simulation.

Core files:

- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/application.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/aiortc_engine.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/outbound_control.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/ports.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/sidecar.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/simplex_session_codec.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/simplex_sidecar.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/tracing.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/voice_turn.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/gateway/calls/native/webrtc_media.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/plugins/platforms/simplex/adapter.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/scripts/simplex_native_sidecar.py`
- `/Users/bryanmurphy/PROJECTS/Hermes-Agent/hermes_cli/calls.py`

The SimpleX signaling approach is:

1. Place or receive a SimpleX call invitation through the SimpleX daemon.
2. Exchange SimpleX call SDP/ICE payloads.
3. Run an `aiortc` peer connection owned by Hermes.
4. Capture remote audio frames.
5. Segment into a voice turn.
6. Run `HermesVoiceTurnPipeline`.
7. Queue local TTS audio into the outbound WebRTC track.

The live path that succeeded used outbound SimpleX calling from Hermes to Bryan's iPhone. The most important accepted live call trace was:

```text
/Users/bryanmurphy/.hermes/profiles/bryan-main/logs/calls/call_0638ec55ea57406bad71d0e51268a7b8.jsonl
```

Bryan confirmed hearing the voice. Treat this as a successful manual spoken-response proof, but not as final product acceptance because weather/tool routing and interruption remain incomplete.

### CLI Debug Commands

The `hermes calls` command family exists for local debugging:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls voice-health --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-health --contact-id 4 --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-watch --contact-id all --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-live-debug --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-call --contact-id 4 --reason codex-test --wait-timeout 30 --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-acceptance --call-id <call-id> --manual-heard --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-simulate-voice-turn --call-id <id> --caller-text "Weather forecast for Leawood Kansas." --expect-transcript weather --timeout 30 --json
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-observe --call-id <call-id> --json
```

`simplex-observe` is the newest command. It summarizes observed STT, agent response, tool intent, and TTS playback state from a trace.

### Observability Added Last

The latest work added opt-in call-turn observability:

- `VoiceDebugTracePolicy` in `gateway/calls/native/voice_turn.py`
- `calls.native.debug.transcript_previews`
- `calls.native.debug.max_preview_chars`
- `voice_turn_transcript_observed`
- `voice_turn_agent_response_observed`
- `tool_intent_observed`
- `simplex-observe` CLI summarization

Defaults are privacy-preserving. In `DEFAULT_CONFIG`, transcript previews are off. In Bryan's local `bryan-main` profile, previews are on with a 240-character cap to support debugging.

The observed preview events are marked `sensitive: true`. No raw audio capture was enabled by default.

Recent simulation used:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-simulate-voice-turn \
  --call-id codex-observe-sim-20260531 \
  --caller-text 'Weather forecast for Leawood Kansas.' \
  --expect-transcript weather \
  --timeout 30 \
  --json
```

It passed:

```json
{
  "ok": true,
  "code": "call_simplex_voice_turn_simulation_passed",
  "connected": true,
  "expected_transcript_present": true,
  "inbound_audio_frames": 417,
  "transcript_chars": 37,
  "agent_response_chars": 202,
  "tts_audio_bytes": 87051,
  "remote_received_audio_frames": 417,
  "remote_received_non_silent_frames": 2
}
```

Observation summary for that trace:

```json
{
  "ok": true,
  "call_id": "codex-observe-sim-20260531",
  "weather_intent_observed": true,
  "turns": [
    {
      "transcript_preview": "weather forecast for Leewood, Kansas.",
      "transcript_chars": 37,
      "stt_provider": "local_command",
      "tool_intents": ["weather"],
      "agent_response_preview": "I can't check real-time weather data. You can look up the forecast for Leewood, Kansas, on a weather website or app for the most accurate and current information. Would you like help with anything else?",
      "agent_response_chars": 202,
      "tts_playback_started": true,
      "tts_playback_completed": false,
      "outbound_audio_received": true
    }
  ]
}
```

This trace proves the new observability caught the exact product issue: STT rendered "Leawood" as "Leewood" and Hermes did not do a real weather lookup.

## Verification Already Run

Focused voice/CLI tests:

```bash
.venv/bin/python -m pytest tests/gateway/test_native_voice_turn.py tests/hermes_cli/test_calls_command.py -q
```

Result:

```text
37 passed
```

Focused SimpleX/native-call regression set:

```bash
.venv/bin/python -m pytest -n0 \
  tests/gateway/test_native_call_application.py \
  tests/gateway/test_simplex_plugin.py \
  tests/gateway/test_native_sidecar.py \
  tests/gateway/test_native_simplex_sidecar_runner.py \
  tests/gateway/test_native_aiortc_engine.py \
  tests/gateway/test_call_command.py \
  tests/gateway/test_native_voice_turn.py \
  tests/hermes_cli/test_calls_command.py \
  -q
```

Result:

```text
203 passed
```

Lint:

```bash
.venv/bin/ruff check \
  gateway/calls/native/voice_turn.py \
  hermes_cli/calls.py \
  hermes_cli/main.py \
  hermes_cli/config.py \
  tests/gateway/test_native_voice_turn.py \
  tests/hermes_cli/test_calls_command.py
```

Result:

```text
All checks passed.
```

Important test-suite caveat: the same focused regression set occasionally failed under parallel pytest because `tests/conftest.py` live-system guard blocked `os.kill` in invalid sidecar response cleanup tests. Each failing sidecar test passed by itself, and the entire focused set passed with `-n0`. Treat this as a test harness/xdist artifact unless it reproduces serially.

## Current Worktree State

The worktree is dirty. Do not assume all changes were made by the current agent. Avoid reverting anything unless Bryan explicitly asks.

Known modified/untracked areas include:

- `agent/codex_runtime.py`
- `gateway/run.py`
- `gateway/calls/native/*`
- `plugins/platforms/simplex/adapter.py`
- `hermes_cli/config.py`
- `hermes_cli/main.py`
- `hermes_cli/calls.py`
- `scripts/simplex_native_sidecar.py`
- SimpleX/native-call tests under `tests/gateway/`
- calls CLI tests under `tests/hermes_cli/`
- `pyproject.toml`
- `uv.lock`

Use `git status --short` before editing, and read nearby diffs before changing any file.

## Known Gaps

### 1. Weather Requests Are Not Fulfilled

The call agent is currently configured with:

```yaml
enabled_toolsets: []
disabled_toolsets:
- terminal
max_iterations: 2
```

This keeps calls lightweight but means a weather request can turn into a generic model answer instead of a deterministic weather lookup. The simulation already reproduced this: Hermes said it could not check real-time weather.

Next steps:

1. Identify the existing Hermes weather tool/toolset, if any.
2. If no safe local weather tool exists, add a narrow deterministic weather tool or allow a specific current-weather API.
3. Configure the native call agent with only the minimal needed toolset.
4. Add a simulation test where caller text asks for weather and acceptance requires a tool-intent event plus tool-backed response.
5. Keep call response short and spoken, not dashboard-style.

### 2. STT Misrecognition Needs Better Handling

Observed issue:

```text
Leawood -> Leewood
```

Next steps:

1. Add optional contact/profile location hints for common place names.
2. Add post-STT normalization for known user context, but keep it auditable in traces.
3. Consider a higher-accuracy local STT backend for calls if latency remains acceptable.
4. Record `stt_confidence` when the backend can provide it.
5. Add traces for `stt_normalization_observed`, including original preview and normalized preview when debug previews are enabled.

### 3. Interruption/Barge-In Is Not Product-Ready

Current path is basically turn-based:

- capture inbound audio;
- wait for enough speech/silence;
- transcribe;
- agent response;
- TTS;
- queue outbound audio.

It does not yet provide strong interruption behavior while Hermes is speaking.

Next steps:

1. Detect inbound speech while outbound TTS is playing.
2. Cancel or fade the queued TTS track on barge-in.
3. Trace `barge_in_detected`, `tts_cancelled`, and `turn_interrupted`.
4. Add a loopback test with inbound audio injected during outbound playback.
5. Add a manual iPhone test where Bryan interrupts Hermes mid-response.

### 4. Live Incoming Call Path Still Needs Final Acceptance

Outbound live calling has worked. Inbound iPhone-to-Hermes calls previously rang, connected, or hung up inconsistently during early debugging.

Next steps:

1. Re-run inbound live debug after the observability patch.
2. Use `simplex-live-debug` to watch the call while Bryan calls, or have Hermes place the call when live verification is needed.
3. Immediately run `simplex-observe --call-id <call-id> --json`.
4. Run `simplex-acceptance --call-id <call-id> --manual-heard --json` only after Bryan confirms he heard the response.
5. Save the final accepted trace path in this document or a follow-up handoff.

### 5. Trace Privacy Needs an Operator Toggle

Debug previews are enabled in Bryan's local profile for now. This is intentional for local debugging, but it should not remain silently enabled forever.

Next steps:

1. Add CLI support to toggle `calls.native.debug.transcript_previews`.
2. Add a visible warning in `simplex-observe` when debug previews are enabled.
3. Consider trace retention/rotation for call traces with speech previews.
4. Keep defaults off in repo config.

### 6. Full Tool/Agent Tracing Is Still Thin

The new `simplex-observe` summary shows STT preview, agent response preview, tool intent, and playback state. It does not yet show the actual Hermes tool calls inside the call agent turn.

Next steps:

1. Add a per-call `session_id` link in the trace.
2. Correlate agent tool calls and model calls with the native call trace.
3. Surface a concise `call_observation_summary` event after each turn.
4. Ensure secrets, contact identifiers, and transcript-sensitive data are redacted or gated.

## Suggested Next Implementation Order

1. Add deterministic weather handling for native voice calls.
2. Add tests that prove a simulated weather utterance produces a tool-backed weather answer.
3. Improve STT normalization for Bryan's common locations and trace it.
4. Implement barge-in cancellation in the outbound TTS track.
5. Add simulation coverage for interruption.
6. Re-run a live call with Bryan only after simulation passes.
7. Update acceptance docs with the final live inbound trace.

## Operational Commands

Restart gateway:

```bash
launchctl kickstart -k gui/$(id -u)/ai.hermes.gateway-bryan-main
```

Inspect gateway service:

```bash
launchctl print gui/$(id -u)/ai.hermes.gateway-bryan-main | sed -n '1,100p'
```

Tail gateway logs:

```bash
tail -f /Users/bryanmurphy/.hermes/profiles/bryan-main/logs/gateway.log
tail -f /Users/bryanmurphy/.hermes/profiles/bryan-main/logs/gateway.error.log
```

List call traces:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls trace
```

Print a trace:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls trace <call-id> -n 200
```

Observe a call turn:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-observe --call-id <call-id> --json
```

Simulate a voice turn:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-simulate-voice-turn \
  --call-id codex-next-sim \
  --caller-text 'Weather forecast for Leawood Kansas.' \
  --expect-transcript weather \
  --timeout 30 \
  --json
```

Ask the running gateway to call Bryan's SimpleX contact:

```bash
.venv/bin/python -m hermes_cli.main --profile bryan-main calls simplex-call \
  --contact-id 4 \
  --reason codex-live-test \
  --wait-timeout 30 \
  --json
```

End the current SimpleX call via daemon websocket, if needed:

```bash
.venv/bin/python - <<'PY'
import asyncio
import json
import uuid
import websockets

async def main():
    async with websockets.connect("ws://127.0.0.1:5225") as ws:
        corr = "codex-end-" + uuid.uuid4().hex
        await ws.send(json.dumps({"corrId": corr, "cmd": "/_call end @4"}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("corrId") == corr:
                print(json.dumps(msg, sort_keys=True))
                return

asyncio.run(main())
PY
```

## Acceptance Checklist Still To Close

- Authorized iPhone SimpleX call is detected, answered, and not immediately dropped.
- WebRTC reaches connected state and remains connected long enough for a spoken turn.
- Hermes receives and decodes inbound audio frames from the iPhone.
- Local STT produces observable text from the spoken input.
- Hermes agent generates a response using the configured model/router.
- Local TTS produces response audio.
- Response audio is injected into the same active SimpleX call and heard on the iPhone.
- Logs/traces show the full lifecycle with secrets, keys, contact identifiers, and transcript-sensitive data redacted or gated.
- A simulation command exercises signaling/media/voice-turn behavior without the phone.
- Final verification includes automated tests plus a manual iPhone spoken round trip.

Current status: the technical loop and simulation are mostly working, and Bryan heard a live response. The remaining acceptance risk is quality and robustness: weather/tool grounding, STT correction, interruption behavior, and repeated inbound-call reliability.
