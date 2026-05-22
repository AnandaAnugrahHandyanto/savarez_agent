"""Send synthesized speech as a native QQ voice message via OneBot.

Registers one LLM-callable tool, ``qq_send_voice``, which turns text into
speech — reusing Hermes's existing ``text_to_speech`` backend (Edge /
OpenAI / ElevenLabs / MiniMax / xAI / Gemini / local NeuTTS, Piper, ...) —
and delivers it as a QQ voice message (语音消息): a real voice bubble, not
a file attachment. It can also send an already-recorded local audio file.

Delivery goes through a running OneBot v11 implementation (NapCat /
Lagrange.Core) using the ``send_msg`` action with a ``record`` message
segment. The audio is embedded inline as a ``base64://`` payload, so
Hermes and the OneBot client do NOT need to share a filesystem (they are
commonly separate Docker containers / hosts). The OneBot client transcodes
the audio to QQ's SILK codec automatically.

Configuration (environment variables) — see ``tools/onebot_client.py``:
- ``ONEBOT_HTTP_URL``     -- base URL of the OneBot HTTP API (required).
- ``ONEBOT_ACCESS_TOKEN`` -- optional bearer token.
The same OneBot connection also powers the ``qzone`` 说说 tool.

Failures (no OneBot connection, TTS misconfiguration, OneBot rejecting the
send) are surfaced verbatim to the model; the tool never silently retries.
Only included in the ``qq_voice`` toolset, so it has zero cost for users on
other platforms.
"""

import base64
import json
import logging
import os

from tools.onebot_client import onebot_call, onebot_configured
from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

# Audio attachment limits. QQ voice messages are short-form; the cap keeps a
# runaway TTS result (or a huge mistaken file path) from posting a giant blob.
_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".amr", ".silk", ".m4a", ".flac", ".aac"}
_MAX_AUDIO_BYTES = 30 * 1024 * 1024  # 30 MiB


# ---------------------------------------------------------------------------
# Targets (pure, unit-tested)
# ---------------------------------------------------------------------------

def _coerce_qq_id(value, field: str) -> int:
    """Coerce a QQ user/group id to a positive int.

    Tolerates ids passed as either an int or a numeric string (the model
    may send either). Raises ``ValueError`` with a human-readable reason.
    """
    try:
        qid = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"'{field}' must be a numeric QQ id, got {value!r}")
    if qid <= 0:
        raise ValueError(f"'{field}' must be a positive QQ id, got {qid}")
    return qid


def _build_record_message(audio_b64: str) -> list:
    """Build the OneBot v11 message array for a single voice (record) segment.

    ``base64://`` lets the OneBot client decode the audio inline, so no
    shared filesystem between Hermes and NapCat/Lagrange is required.
    """
    return [{"type": "record", "data": {"file": f"base64://{audio_b64}"}}]


def _build_send_params(message: list, user_id, group_id) -> dict:
    """Build the OneBot ``send_msg`` params for a private or group target.

    Exactly one of *user_id* / *group_id* must be set; the caller is
    responsible for enforcing that before calling this.
    """
    if group_id is not None:
        return {
            "message_type": "group",
            "group_id": int(group_id),
            "message": message,
        }
    return {
        "message_type": "private",
        "user_id": int(user_id),
        "message": message,
    }


# ---------------------------------------------------------------------------
# Audio payload
# ---------------------------------------------------------------------------

def _read_audio_file(path: str) -> bytes:
    """Read a local audio file, returning its bytes.

    Raises ``ValueError`` with a human-readable reason for any problem so
    the handler can fail fast before touching the network.
    """
    resolved = os.path.expanduser(str(path))
    if not os.path.isfile(resolved):
        raise ValueError("file not found")
    ext = os.path.splitext(resolved)[1].lower()
    if ext not in _AUDIO_EXTS:
        raise ValueError(
            f"unsupported audio type '{ext}' (allowed: {sorted(_AUDIO_EXTS)})"
        )
    size = os.path.getsize(resolved)
    if size == 0:
        raise ValueError("file is empty")
    if size > _MAX_AUDIO_BYTES:
        raise ValueError(
            f"audio too large ({size} bytes; max {_MAX_AUDIO_BYTES})"
        )
    with open(resolved, "rb") as fh:
        return fh.read()


def _synthesize_speech(text: str) -> str:
    """Synthesize *text* to an audio file via Hermes's configured TTS backend.

    Reuses the in-tree ``text_to_speech`` tool — whichever provider and
    voice the user configured under ``tts:`` in ``~/.hermes/config.yaml`` —
    so no new TTS integration is introduced here. Returns the path of the
    generated audio file; raises ``RuntimeError`` on any failure.
    """
    # Imported lazily: tts_tool pulls in heavier optional deps, and a
    # module-level import would couple qq_send_voice's import to it.
    from tools.tts_tool import text_to_speech_tool  # noqa: PLC0415

    raw = text_to_speech_tool(text=text)
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(
            f"text_to_speech returned an unparseable result: {str(raw)[:200]}"
        ) from e

    if not result.get("success"):
        raise RuntimeError(result.get("error") or "speech synthesis failed")
    path = result.get("file_path")
    if not path or not os.path.isfile(path):
        raise RuntimeError("text_to_speech reported success but produced no file")
    return path


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

def _handle_qq_send_voice(args: dict, **kw) -> str:
    """Handler for the qq_send_voice tool."""
    text = (args.get("text") or "").strip()
    audio_file = (args.get("audio_file") or "").strip()

    if not text and not audio_file:
        return tool_error(
            "qq_send_voice requires 'text' (to synthesize) or 'audio_file'."
        )
    if text and audio_file:
        return tool_error(
            "qq_send_voice: provide either 'text' or 'audio_file', not both."
        )

    # Resolve exactly one delivery target.
    raw_user = args.get("user_id")
    raw_group = args.get("group_id")
    has_user = raw_user not in (None, "")
    has_group = raw_group not in (None, "")
    if has_user == has_group:
        return tool_error(
            "qq_send_voice requires exactly one target: 'user_id' (private "
            "chat) or 'group_id' (group chat)."
        )
    try:
        if has_group:
            group_id: int | None = _coerce_qq_id(raw_group, "group_id")
            user_id: int | None = None
        else:
            user_id = _coerce_qq_id(raw_user, "user_id")
            group_id = None
    except ValueError as e:
        return tool_error(f"qq_send_voice: {e}")

    # Resolve the audio payload — from a local file, or freshly synthesized.
    if audio_file:
        try:
            audio_bytes = _read_audio_file(audio_file)
        except ValueError as e:
            return tool_error(f"Audio file '{audio_file}': {e}")
        synthesized = False
    else:
        try:
            audio_path = _synthesize_speech(text)
        except Exception as e:  # noqa: BLE001 — surface one clear message
            logger.error("qq_send_voice: speech synthesis failed: %s", e)
            return tool_error(f"Speech synthesis failed: {e}")
        try:
            audio_bytes = _read_audio_file(audio_path)
        except ValueError as e:
            return tool_error(f"Synthesized audio unusable: {e}")
        synthesized = True

    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
    message = _build_record_message(audio_b64)
    params = _build_send_params(message, user_id, group_id)

    try:
        data = onebot_call("send_msg", params)
    except Exception as e:  # noqa: BLE001 — surface one clear message to the model
        logger.error("qq_send_voice: OneBot send_msg failed: %s", e)
        return tool_error(f"Could not send the voice message via OneBot: {e}")

    target = (
        {"type": "group", "id": group_id}
        if group_id is not None
        else {"type": "private", "id": user_id}
    )
    return json.dumps({
        "success": True,
        "message_id": data.get("message_id"),
        "target": target,
        "synthesized": synthesized,
        "audio_bytes": len(audio_bytes),
        "message": "Voice message sent to QQ.",
    }, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

QQ_SEND_VOICE_SCHEMA = {
    "name": "qq_send_voice",
    "description": (
        "Send a voice message (语音消息) to a QQ user or group — a native "
        "QQ voice bubble, not a file attachment. Give 'text' to synthesize "
        "speech with the user's configured TTS provider/voice, or "
        "'audio_file' to send an existing local audio file. Delivered via a "
        "running OneBot (NapCat / Lagrange) instance. Exactly one of "
        "'user_id' (private chat) or 'group_id' (group chat) is required. "
        "Note: this drives an unofficial automation path and can fail if the "
        "OneBot login state is stale or Tencent risk-control intervenes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to speak. Synthesized to audio with the user's "
                    "configured TTS provider and voice. Provider-specific "
                    "length caps are enforced automatically. Provide this "
                    "OR 'audio_file', not both."
                ),
            },
            "audio_file": {
                "type": "string",
                "description": (
                    "Path to an existing local audio file to send as the "
                    "voice message (mp3, wav, ogg, amr, silk, m4a, flac, "
                    "aac). Provide this OR 'text', not both."
                ),
            },
            "user_id": {
                "type": "string",
                "description": (
                    "Target QQ number for a private-chat voice message. "
                    "Provide either 'user_id' or 'group_id', not both."
                ),
            },
            "group_id": {
                "type": "string",
                "description": (
                    "Target QQ group number for a group-chat voice message. "
                    "Provide either 'user_id' or 'group_id', not both."
                ),
            },
        },
        "required": [],
    },
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="qq_send_voice",
    toolset="qq_voice",
    schema=QQ_SEND_VOICE_SCHEMA,
    handler=_handle_qq_send_voice,
    check_fn=onebot_configured,
    requires_env=["ONEBOT_HTTP_URL"],
    emoji="🎙️",
)
