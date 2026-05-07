# Discord Realtime Voice for Hermes/Ariadne — Codex Implementation Spec

> **For Codex:** Implement this plan in a fresh clone/worktree of `hermes-agent`. Use strict TDD: write failing tests first, run them, implement minimal code, rerun tests, then refactor. Commit in small logical chunks. Do not expose or print secrets.

**Goal:** Add true realtime Discord voice conversation mode to Hermes Agent: Discord voice PCM streams into OpenAI Realtime (`gpt-realtime-2`) and Realtime audio deltas stream back into Discord, with interruption/barge-in and a safe path for Hermes tools.

**Non-goal:** Do not replace existing `/voice channel` turn-based STT → LLM → TTS behavior. Keep it as a fallback.

**Architecture:** Keep Discord voice as the user interface. Add a new `/voice realtime` mode that uses the existing Discord Opus→PCM receiver but streams frames directly to OpenAI Realtime over server-side WebSocket. Create a Discord `AudioSource` that consumes streaming PCM output from Realtime and plays it into the voice channel.

**Tech Stack:** Python 3.11+, `discord.py[voice]`, `aiohttp`, OpenAI Realtime WebSocket, PCM16 audio, pytest/pytest-asyncio.

---

## Current Code Context

Repo path on target machine:

```bash
/home/rationallyprime/.hermes/hermes-agent
```

Important files:

- `gateway/platforms/discord.py`
  - `VoiceReceiver` starts around line 121.
  - It currently decrypts RTP, decodes Opus to PCM, buffers per-user audio, and returns completed utterances via `check_silence()`.
  - `_voice_listen_loop()` starts around line 1834.
  - `_process_voice_input()` starts around line 1866 and converts buffered PCM to WAV, then transcribes.
  - `join_voice_channel()` starts around line 1610.
  - `play_in_voice_channel()` starts around line 1668 and plays whole audio files.
- `gateway/run.py`
  - `_handle_voice_command()` starts around line 8314.
  - `_handle_voice_channel_join()` starts around line 8391.
  - `_handle_voice_channel_input()` starts around line 8516.
  - `_send_voice_reply()` starts around line 8638.
- `pyproject.toml`
  - `messaging` extra already has `discord.py[voice]` and `aiohttp`.
  - `voice` extra has `sounddevice` and `numpy` but realtime Discord mode should not require microphone capture.

Existing voice mode is **not realtime**. It waits for silence, transcribes a WAV file, runs the normal text agent loop, generates a TTS file, then plays that file.

Docs context: `https://hermes-agent.nousresearch.com/docs/guides/use-voice-mode-with-hermes` calls this a "Live voice channel bot" and describes Discord VC mode as detecting speech boundaries, posting transcripts, running the normal agent pipeline, and speaking replies. That is live-in-a-voice-channel, but not true streaming realtime speech-to-speech. The new mode should be named distinctly (`/voice realtime` / `/voice live`) and the docs should clarify the difference.

New realtime mode should instead be:

```text
Discord RTP/Opus → decoded PCM frames → OpenAI Realtime input_audio_buffer.append
OpenAI response.output_audio.delta → PCM queue → Discord AudioSource.read() → voice channel
```

---

## OpenAI Realtime Requirements

Use server-side WebSocket because Discord bot voice is a server media pipeline. Browser/mobile clients would use WebRTC, but this is not a browser client.

Connection:

```text
wss://api.openai.com/v1/realtime?model=gpt-realtime-2
Use the Authorization header with the selected OpenAI API key from `VOICE_TOOLS_OPENAI_KEY` or `OPENAI_API_KEY`; never log the value.
OpenAI-Safety-Identifier: stable hashed user id if available
```

Core client events:

- `session.update`
- `input_audio_buffer.append`
- `input_audio_buffer.clear` when needed
- `response.cancel` or equivalent cancellation event when barge-in occurs, if supported by current API
- `conversation.item.create` with `function_call_output` for function tools
- `response.create` after function output when needed

Core server events to handle:

- `session.created`
- `session.updated`
- `input_audio_buffer.speech_started`
- `input_audio_buffer.speech_stopped`
- `response.output_audio.delta`
- `response.audio.delta` too, for compatibility with older/newer docs/examples
- `response.output_audio.done`
- `response.output_audio_transcript.delta`
- `response.output_audio_transcript.done`
- `response.output_item.done`
- `response.done`
- error events

Initial `session.update` should be close to:

```python
{
    "type": "session.update",
    "session": {
        "type": "realtime",
        "model": "gpt-realtime-2",
        "output_modalities": ["audio"],
        "instructions": realtime_instructions,
        "audio": {
            "input": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "turn_detection": {
                    "type": "semantic_vad",
                    "interrupt_response": True,
                    "create_response": True,
                },
            },
            "output": {
                "format": {"type": "audio/pcm", "rate": 24000},
                "voice": configured_voice,
            },
        },
        "tools": realtime_tools,
        "tool_choice": "auto",
    },
}
```

If the deployed API rejects this shape, adapt to the current official API shape, but preserve these semantics:

- model: `gpt-realtime-2`
- input: PCM16 24 kHz mono
- output: PCM16 24 kHz mono
- VAD enabled
- interruption enabled
- audio output enabled

---

## Config Requirements

Add config keys under `voice.realtime` without breaking existing `voice` keys:

```yaml
voice:
  realtime:
    enabled: true
    provider: openai
    model: gpt-realtime-2
    voice: marin
    input_rate: 24000
    output_rate: 24000
    turn_detection: semantic_vad
    tools_enabled: false
    idle_timeout_seconds: 300
    max_session_minutes: 30
```

Default `tools_enabled` to `false` for the MVP unless approval bridge is complete and tested. Realtime speech alone is useful; unsafe tool execution is not.

Credential lookup order:

1. `VOICE_TOOLS_OPENAI_KEY`
2. `OPENAI_API_KEY`

Never print key values.

---

## Audio Format Requirements

Discord voice input from `discord.opus.Decoder().decode(...)` is PCM16:

- 48 kHz
- stereo
- signed 16-bit little-endian
- normally 20 ms frames

OpenAI Realtime input/output should be PCM16:

- 24 kHz
- mono
- signed 16-bit little-endian

Need two conversion paths:

1. Discord input → Realtime input:

```text
48k stereo PCM16 → 24k mono PCM16
```

2. Realtime output → Discord playback:

```text
24k mono PCM16 → 48k stereo PCM16
```

Acceptable MVP implementation:

- Use stdlib `audioop` on Python 3.11/3.12.
- Add `audioop-lts>=0.2.1,<1; python_version >= '3.13'` if needed for Python 3.13 compatibility.
- Hide `audioop` behind helper functions so it can be swapped later.

Do not shell out to ffmpeg per frame; too slow for realtime.

---

## New File: `gateway/discord_realtime_audio.py`

Create this file.

### Public API

```python
class RealtimeDiscordAudioSource(discord.AudioSource):
    def __init__(self, *, input_rate: int = 24000, discord_rate: int = 48000): ...
    def is_opus(self) -> bool: ...
    def read(self) -> bytes: ...
    def push_pcm_24k_mono(self, pcm: bytes) -> None: ...
    def clear(self) -> None: ...
    def close(self) -> None: ...
```

`read()` must return exactly one Discord PCM frame:

- 20 ms at 48 kHz stereo PCM16
- `3840` bytes: `48000 * 0.02 * 2 channels * 2 bytes`

If the output queue is empty, return `3840` bytes of silence, not `b''`. Returning `b''` tells Discord playback to stop.

### Helper functions

```python
def discord_pcm_to_realtime_pcm(pcm_48k_stereo: bytes) -> bytes:
    """48k stereo PCM16 -> 24k mono PCM16."""


def realtime_pcm_to_discord_pcm(pcm_24k_mono: bytes) -> bytes:
    """24k mono PCM16 -> 48k stereo PCM16."""
```

### Tests

Create `tests/gateway/test_discord_realtime_audio.py`.

Required tests:

1. `test_read_returns_silence_frame_when_queue_empty`
   - Instantiate source.
   - Call `read()`.
   - Assert length is `3840`.
   - Assert all bytes are zero.

2. `test_push_pcm_outputs_discord_sized_frames`
   - Push 100 ms of 24 kHz mono silence: `2400 samples * 2 bytes = 4800 bytes`.
   - Call `read()` several times.
   - Assert each frame length is `3840`.

3. `test_clear_drops_buffered_audio`
   - Push nonzero PCM.
   - Clear.
   - Read.
   - Assert silence frame.

4. `test_resampler_roundtrip_lengths_are_reasonable`
   - Generate 20 ms of 48k stereo silence: `3840` bytes.
   - Convert to realtime.
   - Assert output is 20 ms of 24k mono: `960` bytes.
   - Convert back.
   - Assert output is `3840` bytes.

Commands:

```bash
python -m pytest tests/gateway/test_discord_realtime_audio.py -q
```

---

## New File: `gateway/realtime_voice.py`

Create this file.

### Public API

```python
@dataclass
class RealtimeVoiceConfig:
    api_key: str
    model: str = "gpt-realtime-2"
    voice: str = "marin"
    instructions: str = ""
    safety_identifier: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    tools_enabled: bool = False


class RealtimeVoiceSession:
    def __init__(
        self,
        *,
        config: RealtimeVoiceConfig,
        audio_sink: Callable[[bytes], None],
        on_transcript: Callable[[str, str], Awaitable[None]] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[str]] | None = None,
        logger: logging.Logger | None = None,
    ): ...

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def append_discord_pcm(self, user_id: int, pcm_48k_stereo: bytes) -> None: ...
```

### Behavior

- `start()` opens the WebSocket and sends `session.update`.
- `stop()` closes tasks and the WebSocket cleanly.
- `append_discord_pcm()` converts 48k stereo to 24k mono and queues/sends `input_audio_buffer.append` with base64 PCM.
- Receiver loop parses JSON events.
- On audio delta events, base64-decode and call `audio_sink(pcm_24k_mono)`.
- On `input_audio_buffer.speech_started`, call `audio_sink.clear()` if available or expose a separate `on_barge_in` callback. This clears queued bot audio for interruption.
- Log errors without killing the gateway if possible.

### Tool handling

MVP: if `tools_enabled` is false, send no tools.

If enabled:

- Accept Realtime function tools in OpenAI format:

```python
{
    "type": "function",
    "name": "tool_name",
    "description": "...",
    "parameters": {...},
}
```

- Detect function calls from `response.output_item.done` where `item.type == "function_call"`.
- Parse `item.arguments` JSON.
- Run `tool_executor(item.name, arguments)`.
- Send:

```python
{
    "type": "conversation.item.create",
    "item": {
        "type": "function_call_output",
        "call_id": item["call_id"],
        "output": output_string,
    },
}
```

- Then send `{"type": "response.create"}`.

Do not enable this path by default until approval bridge is wired through `gateway/run.py`.

### Tests

Create `tests/gateway/test_realtime_voice.py` with mocked WebSocket/client.

Required tests:

1. `test_start_sends_session_update`
   - Mock WS.
   - Start session.
   - Assert first outbound event is `session.update` with model, voice, audio config.

2. `test_append_discord_pcm_sends_base64_audio_append`
   - Start session with fake WS.
   - Append one Discord silence frame.
   - Assert an `input_audio_buffer.append` event is sent.
   - Assert `audio` field is base64 string.

3. `test_audio_delta_is_forwarded_to_sink`
   - Feed fake server event `response.output_audio.delta` with base64 PCM.
   - Assert sink receives decoded bytes.

4. `test_legacy_audio_delta_name_is_forwarded_to_sink`
   - Same for `response.audio.delta`.

5. `test_speech_started_clears_sink_when_supported`
   - Use sink object with `clear()` method.
   - Feed `input_audio_buffer.speech_started`.
   - Assert `clear()` called.

6. `test_function_call_executes_tool_and_returns_output_when_enabled`
   - Enable tools.
   - Feed `response.output_item.done` function call event.
   - Assert `tool_executor` called.
   - Assert outbound `conversation.item.create` with `function_call_output`.
   - Assert outbound `response.create`.

Commands:

```bash
python -m pytest tests/gateway/test_realtime_voice.py -q
```

---

## Modify `gateway/platforms/discord.py`

### Add realtime streaming support to `VoiceReceiver`

Keep legacy buffering intact.

Add fields:

```python
self._realtime_enabled = False
self._realtime_audio_callback = None
self._realtime_loop = None
```

Add method:

```python
def set_realtime_callback(self, loop: asyncio.AbstractEventLoop, callback: Callable[[int, bytes], None] | None):
    self._realtime_loop = loop
    self._realtime_audio_callback = callback
    self._realtime_enabled = callback is not None
```

In `_on_packet`, after Opus decode and user mapping:

```python
if self._realtime_enabled and self._realtime_audio_callback and self._realtime_loop:
    user_id = self._ssrc_to_user.get(ssrc, 0) or self._infer_user_for_ssrc(ssrc)
    if user_id:
        self._realtime_loop.call_soon_threadsafe(
            self._realtime_audio_callback,
            user_id,
            pcm,
        )
```

Important:

- Do not pause receiver while bot is speaking in realtime mode.
- Avoid feeding bot’s own audio back; existing `if ssrc == self._bot_ssrc: return` should handle this.
- Preserve legacy buffering/check_silence for `/voice channel`.

### Add adapter state

In `DiscordAdapter.__init__` add:

```python
self._realtime_voice_sessions: Dict[int, Any] = {}
self._realtime_audio_sources: Dict[int, Any] = {}
self._realtime_context_factory: Optional[Callable] = None
```

### Add realtime join method

Preferred: add a separate method rather than overloading too much:

```python
async def join_realtime_voice_channel(self, channel, realtime_context: Any) -> bool:
    ...
```

Behavior:

1. Connect to the Discord voice channel like `join_voice_channel()`.
2. Create `RealtimeDiscordAudioSource`.
3. Call `voice_client.play(source)` once. Source returns silence when idle, so playback stays alive.
4. Create `RealtimeVoiceSession` with:
   - config from `realtime_context`
   - `audio_sink=source.push_pcm_24k_mono`
   - barge-in clear wired to source.clear, if designed separately
5. Start session.
6. Create/start `VoiceReceiver` if not already running.
7. Set receiver realtime callback to schedule `session.append_discord_pcm(user_id, pcm)`.
8. Store session/source in dicts by guild id.
9. Do not start `_voice_listen_loop` for realtime mode.

### Update leave/disconnect

When leaving voice, also stop realtime session and close source:

```python
session = self._realtime_voice_sessions.pop(guild_id, None)
if session:
    await session.stop()
source = self._realtime_audio_sources.pop(guild_id, None)
if source:
    source.close()
```

### Tests

Create `tests/gateway/platforms/test_discord_realtime_voice.py` if practical, or add to existing gateway tests.

Required behavior-level tests using fakes/mocks:

1. `test_voice_receiver_realtime_callback_receives_pcm`
   - Mock decoded PCM path if necessary.
   - Verify callback gets `(user_id, pcm)`.

2. `test_leave_voice_stops_realtime_session`
   - Fake adapter state with mock session/source.
   - Call leave.
   - Assert `stop()` and `close()` called.

3. `test_legacy_voice_receiver_buffering_still_works`
   - Ensure adding realtime callback does not remove buffer behavior unless explicitly disabled.

---

## Modify `gateway/run.py`

### Add command syntax

Support these aliases:

```text
/voice realtime
/voice live
/voice channel realtime
```

Also preserve/normalize docs-facing legacy join aliases:

```text
/voice join      # alias for current turn-based /voice channel
/voice channel   # existing turn-based behavior
```

Keep existing:

```text
/voice channel
/voice leave
/voice status
/voice on
/voice tts
/voice off
```

### Behavior

- `/voice channel` remains current turn-based behavior.
- `/voice realtime` joins the invoking user’s voice channel and starts true streaming mode.
- `/voice leave` stops either realtime or legacy mode.
- `/voice status` should report whether realtime is active.

### New method

Add:

```python
async def _handle_voice_realtime_join(self, event: MessageEvent) -> str:
    ...
```

Responsibilities:

1. Confirm platform is Discord.
2. Confirm event is from a guild/server context, not DM-only.
3. Confirm user is in a Discord voice channel.
4. Build realtime context/config:
   - API key from env.
   - model from `voice.realtime.model`, default `gpt-realtime-2`.
   - voice from `voice.realtime.voice`, default `marin`.
   - instructions based on Hermes/Ariadne persona, but concise for realtime.
   - tools disabled by default.
5. Call adapter `join_realtime_voice_channel(...)`.
6. Return a short text confirmation.

### Realtime instructions

Use a concise system instruction for low latency, e.g.:

```text
You are Ariadne, Hákon's operational AI assistant. This is a live voice conversation. Be brief, direct, and conversational. Do not narrate tool use. Ask at most one clarifying question when needed. For external side effects or risky operations, say you need explicit approval and wait. If asked to do internet/system/file work that requires tools unavailable in this realtime session, summarize the intended action and ask Hákon to send it as text or approve handoff to the normal Hermes tool loop.
```

### Tool integration policy

MVP should ship with realtime tools disabled unless approval bridge is implemented. That is acceptable.

If implementing tool calls in this PR:

- Extract the existing gateway approval setup into a reusable helper.
- Realtime tool executor must call the same `model_tools.handle_function_call(...)` path normal Hermes uses.
- Dangerous tools must block until Discord `/approve` or `/deny`, same as normal text mode.
- Add tests proving a pending approval blocks tool completion.

If this is too large, leave a clear TODO and set `tools_enabled: false` by default.

---

## Modify command registration/help if needed

Find slash command definitions for `/voice` in `gateway/platforms/discord.py` around line 2656 and any central command registry in `hermes_cli/commands.py`.

Add visible choices if feasible:

- `realtime` — true low-latency speech-to-speech voice session
- `live` — alias for realtime

If Discord app command cap blocks updating global slash commands, plain text `/voice realtime` must still work.

---

## Dependency Changes

Only add dependencies if needed.

Preferred: no new runtime dependency beyond existing `aiohttp` and `discord.py[voice]`.

If using `audioop` helpers and Python 3.13 compatibility is required, add to `pyproject.toml`:

```toml
audioop-lts>=0.2.1,<1; python_version >= '3.13'
```

Place it in `messaging` or core only if imports are guarded. Prefer `messaging`.

---

## Acceptance Criteria

Functional:

- `/voice realtime` joins the user’s current Discord voice channel.
- Speaking in the channel streams audio to OpenAI Realtime without waiting for a full utterance WAV.
- Ariadne speaks back with streaming audio in the same Discord voice channel.
- User speech while Ariadne is speaking clears queued output / interrupts response.
- `/voice leave` stops Realtime session and Discord playback cleanly.
- Existing `/voice channel` legacy mode still works.
- Gateway does not crash if OpenAI Realtime connection fails; user gets a useful error.

Safety:

- No API keys are logged or printed.
- Tool calls are disabled by default unless approval bridge is completed.
- If tool calls are enabled, dangerous operations use the same approval flow as normal Hermes.

Tests:

- New unit tests pass.
- Relevant existing voice/gateway tests pass.
- Full non-integration suite passes or known unrelated failures are documented.

---

## Exact Test Commands

Use the repo venv if present:

```bash
cd /home/rationallyprime/.hermes/hermes-agent
source venv/bin/activate  # or .venv/bin/activate if present
```

Run targeted tests:

```bash
python -m pytest tests/gateway/test_discord_realtime_audio.py -q
python -m pytest tests/gateway/test_realtime_voice.py -q
python -m pytest tests/gateway/test_voice_command.py -q
python -m pytest tests/gateway/test_voice_mode_platform_isolation.py -q
python -m pytest tests/tools/test_voice_mode.py -q
```

Run broader suite without xdist if debugging:

```bash
python -m pytest tests/gateway tests/tools/test_voice_mode.py -o 'addopts=' -q
```

Run configured suite if time allows:

```bash
python -m pytest tests/ -q
```

---

## Manual Test Procedure on Hákon's Machine

After implementation is merged/cloned locally:

1. Ensure config has OpenAI key in `.env` as `VOICE_TOOLS_OPENAI_KEY` or `OPENAI_API_KEY`.
2. Set config:

```bash
hermes config set voice.realtime.enabled true
hermes config set voice.realtime.model gpt-realtime-2
hermes config set voice.realtime.voice marin
hermes config set voice.realtime.tools_enabled false
```

3. Restart gateway:

```bash
systemctl --user restart hermes-gateway
systemctl --user status hermes-gateway --no-pager --lines=20
```

4. Join a Discord server voice channel where the bot has Connect + Speak.
5. In a text channel the bot can read, send:

```text
/voice realtime
```

6. Speak normally.
7. While Ariadne is speaking, interrupt her. Expected: queued speech stops/clears quickly and she responds to new speech.
8. Stop:

```text
/voice leave
```

9. Check logs if needed:

```bash
journalctl --user -u hermes-gateway -n 200 --no-pager
```

Look for:

- OpenAI Realtime connection errors
- audio conversion exceptions
- Discord voice playback stopped unexpectedly
- secrets accidentally logged

---

## Suggested Commit Breakdown

1. `test: add realtime discord audio source tests`
2. `feat: add realtime discord audio source`
3. `test: add realtime voice websocket session tests`
4. `feat: add realtime voice websocket session`
5. `test: cover discord realtime voice lifecycle`
6. `feat: stream discord voice through realtime session`
7. `feat: add voice realtime command`
8. `docs: document realtime voice setup`

---

## Codex Execution Prompt

Use this prompt in the cloud Codex sandbox after cloning the repo:

```text
Implement true realtime Discord voice mode for Hermes Agent according to docs/plans/2026-05-07-discord-realtime-voice-codex-spec.md.

Constraints:
- Use strict TDD. Write failing tests first and run them before production code.
- Keep existing /voice channel legacy behavior working.
- Add /voice realtime and /voice live as true streaming OpenAI Realtime modes.
- Use OpenAI Realtime WebSocket with gpt-realtime-2 for server-side Discord audio.
- Do not print or log API keys or secrets.
- Disable realtime tool calls by default unless you fully wire and test existing Hermes approval flow.
- Prefer no new runtime deps beyond aiohttp/discord.py; only add audioop-lts for Python >=3.13 if needed.
- Commit in small logical chunks.

When done, provide:
1. git diff summary
2. tests run + outputs
3. any manual testing notes
4. any skipped acceptance criteria
```

---

## Review Checklist

Before accepting the PR/patch:

- [ ] Does `/voice channel` still use old turn-based flow?
- [ ] Does `/voice realtime` avoid WAV/STT/TTS file path entirely?
- [ ] Does Discord `AudioSource.read()` return silence instead of `b''` when idle?
- [ ] Does barge-in clear queued output?
- [ ] Are OpenAI event names current and tolerant of documented aliases?
- [ ] Are secrets never logged?
- [ ] Are realtime tools disabled by default or approval-safe?
- [ ] Do targeted tests pass?
- [ ] Is gateway failure graceful if OpenAI Realtime is unavailable?
