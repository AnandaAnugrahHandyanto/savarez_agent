"""OpenRouter audio generation backend.

Surface: text-to-audio (music, soundscapes) through OpenRouter's
audio-output chat models. One ``OPENROUTER_API_KEY`` routes to Google's
Lyria 3 (music with optional vocals/lyrics) and OpenAI's GPT-Audio — the
same key the agent already uses for its main model, so no extra setup is
needed when Hermes runs on OpenRouter.

Why chat/completions: OpenRouter has **no** dedicated ``/audio/generate``
endpoint. Music / sound models are ordinary chat-completions models that
declare ``audio`` in their output modalities. We call
``POST /chat/completions`` with ``modalities: ["audio"]`` and read the
base64 audio out of ``choices[0].message.audio.data``.

Flow:
  1. ``POST {base}/chat/completions`` with the prompt as the user message,
     ``modalities: ["audio"]`` and ``audio: {format}``.
  2. Decode ``message.audio.data`` (base64) and write it to the audio-gen
     cache; return the absolute path. The gateway delivers the file.

Model discovery: the audio-output catalog is fetched live from
``GET {base}/models`` filtered on ``architecture.output_modalities``
containing ``"audio"``, cached for the process, with a small static
fallback when the network call fails.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from agent.audio_gen_provider import (
    COMMON_AUDIO_FORMATS,
    DEFAULT_AUDIO_FORMAT,
    AudioGenProvider,
    error_response,
    save_b64_audio,
    success_response,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "google/lyria-3-pro-preview"
DEFAULT_TIMEOUT_SECONDS = 300
MODELS_CACHE_TTL_SECONDS = 3600

# OpenRouter audio output is delivered as wav or mp3 (the ChatAudioOutput
# format field). We default to mp3 and only forward formats we know the
# chat-audio path accepts.
_SUPPORTED_FORMATS = ("mp3", "wav")

# Static fallback catalog — used only when the live /models call fails
# (offline, transient error). The live fetch is the source of truth.
# NOT asserted by any test (catalog data changes upstream).
_FALLBACK_MODELS: List[Dict[str, Any]] = [
    {
        "id": "google/lyria-3-pro-preview",
        "display": "Lyria 3 Pro",
        "strengths": "Music, 48kHz stereo, optional vocals + lyrics",
        "kinds": ["music"],
        "supports_lyrics": True,
    },
    {
        "id": "google/lyria-3-clip-preview",
        "display": "Lyria 3 Clip",
        "strengths": "Short music clips with vocals",
        "kinds": ["music"],
        "supports_lyrics": True,
    },
    {
        "id": "openai/gpt-audio",
        "display": "GPT-Audio",
        "strengths": "General audio output",
        "kinds": ["music", "sfx"],
        "supports_lyrics": False,
    },
    {
        "id": "openai/gpt-audio-mini",
        "display": "GPT-Audio Mini",
        "strengths": "Fast, lower-cost audio output",
        "kinds": ["music", "sfx"],
        "supports_lyrics": False,
    },
]

# Process-wide cache for the live audio-model catalog: (timestamp, models).
_models_cache: tuple[float, List[Dict[str, Any]]] | None = None


# ---------------------------------------------------------------------------
# Credential + HTTP helpers
# ---------------------------------------------------------------------------


def _resolve_credentials() -> tuple[str, str]:
    """Return ``(api_key, base_url)`` from the shared OpenRouter resolver."""
    try:
        from tools.tool_backend_helpers import resolve_openrouter_credentials

        creds = resolve_openrouter_credentials()
        return creds["api_key"], creds["base_url"]
    except Exception as exc:  # noqa: BLE001
        logger.debug("OpenRouter credential resolver failed: %s", exc)
        return "", "https://openrouter.ai/api/v1"


def _headers(api_key: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/NousResearch/hermes-agent",
        "X-Title": "Hermes Agent",
    }


def _fetch_models() -> List[Dict[str, Any]]:
    """Fetch the live audio-output model catalog, cached for the process.

    Filters ``GET /models`` on ``architecture.output_modalities`` containing
    ``"audio"``. On any failure returns the static fallback so the picker /
    capabilities never crash on a network blip.
    """
    global _models_cache
    now = time.time()
    if _models_cache is not None and (now - _models_cache[0]) < MODELS_CACHE_TTL_SECONDS:
        return _models_cache[1]

    api_key, base_url = _resolve_credentials()
    if not api_key:
        return _FALLBACK_MODELS
    try:
        resp = httpx.get(
            f"{base_url}/models",
            headers=_headers(api_key),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        out: List[Dict[str, Any]] = []
        for entry in data if isinstance(data, list) else []:
            arch = entry.get("architecture") or {}
            out_modalities = arch.get("output_modalities") or []
            if "audio" not in out_modalities:
                continue
            mid = entry.get("id")
            if not mid:
                continue
            out.append({
                "id": mid,
                "display": entry.get("name", mid),
                "strengths": (entry.get("description") or "")[:120],
                "kinds": ["music"],
                # Heuristic: Lyria models do vocals/lyrics.
                "supports_lyrics": "lyria" in mid.lower(),
            })
        if out:
            _models_cache = (now, out)
            return out
    except Exception as exc:  # noqa: BLE001
        logger.debug("OpenRouter audio model fetch failed: %s", exc)
    return _FALLBACK_MODELS


def _model_entry(model_id: str) -> Optional[Dict[str, Any]]:
    """Return the catalog entry for *model_id*, or None."""
    for entry in _fetch_models():
        if entry.get("id") == model_id:
            return entry
    return None


def _clamp_format(audio_format: Optional[str]) -> str:
    fmt = (audio_format or DEFAULT_AUDIO_FORMAT).strip().lower()
    return fmt if fmt in _SUPPORTED_FORMATS else "mp3"


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OpenRouterAudioGenProvider(AudioGenProvider):
    """OpenRouter audio backend (music / audio from a text prompt)."""

    @property
    def name(self) -> str:
        return "openrouter"

    @property
    def display_name(self) -> str:
        return "OpenRouter"

    def is_available(self) -> bool:
        api_key, _ = _resolve_credentials()
        return bool(api_key)

    def list_models(self) -> List[Dict[str, Any]]:
        return list(_fetch_models())

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "OpenRouter Audio",
            "badge": "paid",
            "tag": (
                "One OpenRouter key for Lyria 3 music + GPT-Audio — "
                "text-to-music with optional lyrics; uses OPENROUTER_API_KEY"
            ),
            "env_vars": [
                {
                    "key": "OPENROUTER_API_KEY",
                    "prompt": "OpenRouter API key",
                    "url": "https://openrouter.ai/keys",
                },
            ],
        }

    def capabilities(self) -> Dict[str, Any]:
        supports_lyrics = any(
            entry.get("supports_lyrics") for entry in _fetch_models()
        )
        return {
            "kinds": ["music", "sfx"],
            "formats": list(_SUPPORTED_FORMATS),
            "max_duration": 60,
            "min_duration": 1,
            "supports_lyrics": supports_lyrics,
            "supports_negative_prompt": False,
        }

    def generate(
        self,
        prompt: str,
        *,
        model: Optional[str] = None,
        duration: Optional[int] = None,
        audio_format: str = DEFAULT_AUDIO_FORMAT,
        negative_prompt: Optional[str] = None,
        lyrics: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        api_key, base_url = _resolve_credentials()
        if not api_key:
            return error_response(
                error=(
                    "No OpenRouter credentials found. Set OPENROUTER_API_KEY "
                    "(https://openrouter.ai/keys) or run `hermes setup`."
                ),
                error_type="auth_required",
                provider="openrouter", prompt=prompt,
            )

        prompt = (prompt or "").strip()
        if not prompt:
            return error_response(
                error="prompt is required for OpenRouter audio generation",
                error_type="missing_prompt",
                provider="openrouter", prompt=prompt,
            )

        resolved_model = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
        fmt = _clamp_format(audio_format)

        # Build the user message. Lyrics ride along in the prompt text so
        # Lyria's song mode picks them up; instrumental models ignore them.
        user_content = prompt
        if lyrics:
            user_content = f"{prompt}\n\nLyrics:\n{lyrics.strip()}"
        if duration:
            try:
                user_content = f"{user_content}\n\nTarget duration: ~{int(duration)} seconds."
            except (TypeError, ValueError):
                pass

        payload: Dict[str, Any] = {
            "model": resolved_model,
            "modalities": ["audio"],
            "audio": {"format": fmt},
            "messages": [{"role": "user", "content": user_content}],
        }
        if seed is not None:
            payload["seed"] = seed

        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers=_headers(api_key),
                json=payload,
                timeout=DEFAULT_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.text[:500]
            except Exception:
                pass
            return error_response(
                error=f"OpenRouter audio request failed ({exc.response.status_code}): {detail or exc}",
                error_type="api_error",
                provider="openrouter", model=resolved_model, prompt=prompt,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenRouter audio gen unexpected failure: %s", exc, exc_info=True)
            return error_response(
                error=f"OpenRouter audio generation failed: {exc}",
                error_type="api_error",
                provider="openrouter", model=resolved_model, prompt=prompt,
            )

        try:
            body = resp.json()
            choices = body.get("choices") or []
            message = choices[0].get("message") if choices else None
            audio_obj = (message or {}).get("audio") if isinstance(message, dict) else None
            b64 = (audio_obj or {}).get("data") if isinstance(audio_obj, dict) else None
        except Exception as exc:  # noqa: BLE001
            return error_response(
                error=f"OpenRouter audio response could not be parsed: {exc}",
                error_type="empty_response",
                provider="openrouter", model=resolved_model, prompt=prompt,
            )

        if not b64:
            return error_response(
                error=(
                    "OpenRouter audio response did not include audio data. "
                    "The selected model may not support audio output — pick "
                    "a Lyria or GPT-Audio model via `hermes tools` → Audio "
                    "Generation."
                ),
                error_type="empty_response",
                provider="openrouter", model=resolved_model, prompt=prompt,
            )

        try:
            path = save_b64_audio(b64, prefix="openrouter", extension=fmt)
        except Exception as exc:  # noqa: BLE001
            return error_response(
                error=f"Could not save OpenRouter audio: {exc}",
                error_type="io_error",
                provider="openrouter", model=resolved_model, prompt=prompt,
            )

        extra: Dict[str, Any] = {}
        if isinstance(body.get("usage"), dict):
            extra["usage"] = body["usage"]
        transcript = (audio_obj or {}).get("transcript") if isinstance(audio_obj, dict) else None
        if transcript:
            extra["transcript"] = transcript

        return success_response(
            audio=str(path),
            model=resolved_model,
            prompt=prompt,
            duration=int(duration) if duration else 0,
            audio_format=fmt,
            provider="openrouter",
            extra=extra or None,
        )


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------


def register(ctx) -> None:
    """Plugin entry point — wire ``OpenRouterAudioGenProvider`` into the registry."""
    ctx.register_audio_gen_provider(OpenRouterAudioGenProvider())
