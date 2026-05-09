"""Google Gemini / Nano Banana image generation backend.

Implements Hermes' :class:`ImageGenProvider` interface using the Gemini
GenerateContent REST API directly. This avoids adding google-genai/Pillow as
runtime dependencies while still supporting Gemini's native image models.

Key selection precedence:
1. ``GEMINI_API_KEY``
2. ``GOOGLE_API_KEY``
3. ``NANO_BANANA_API_KEY`` (Palmer-local alias; value is never logged)

Model selection precedence:
1. ``GEMINI_IMAGE_MODEL`` env var
2. ``image_gen.gemini.model`` in ``config.yaml``
3. ``image_gen.model`` in ``config.yaml`` when it is one of this backend's IDs
4. ``gemini-2.5-flash-image``
"""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)

API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash-image"
DEFAULT_IMAGE_SIZE = "1K"
_KEY_ENV_VARS = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "NANO_BANANA_API_KEY")

_MODELS: Dict[str, Dict[str, Any]] = {
    "gemini-2.5-flash-image": {
        "display": "Gemini 2.5 Flash Image (Nano Banana)",
        "speed": "fast",
        "strengths": "Speed/efficiency for routine image generation",
        "price": "Google Gemini API pricing",
    },
    "gemini-3.1-flash-image-preview": {
        "display": "Gemini 3.1 Flash Image Preview (Nano Banana 2)",
        "speed": "fast",
        "strengths": "High-efficiency Gemini 3 image generation",
        "price": "Google Gemini API pricing",
    },
    "gemini-3-pro-image-preview": {
        "display": "Gemini 3 Pro Image Preview (Nano Banana Pro)",
        "speed": "slower",
        "strengths": "Professional/high-fidelity assets and text rendering",
        "price": "Google Gemini API pricing",
    },
}

_ASPECT_RATIOS = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}

_IMAGE_SIZES = {"512", "1K", "2K", "4K"}


def _load_image_gen_config() -> Dict[str, Any]:
    """Read ``image_gen`` config, returning {} on any failure."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen config: %s", exc)
        return {}


def _resolve_api_key() -> Tuple[str, str]:
    """Return ``(api_key, env_var_name)`` without logging or exposing the key."""
    for name in _KEY_ENV_VARS:
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    return "", ""


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    env_override = os.getenv("GEMINI_IMAGE_MODEL", "").strip()
    if env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_image_gen_config()
    gemini_cfg = cfg.get("gemini") if isinstance(cfg.get("gemini"), dict) else {}
    candidate: Optional[str] = None
    if isinstance(gemini_cfg, dict):
        value = gemini_cfg.get("model")
        if isinstance(value, str) and value.strip() in _MODELS:
            candidate = value.strip()

    if candidate is None:
        value = cfg.get("model")
        if isinstance(value, str) and value.strip() in _MODELS:
            candidate = value.strip()

    if candidate is not None:
        return candidate, _MODELS[candidate]
    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _resolve_image_size() -> str:
    env_size = os.getenv("GEMINI_IMAGE_SIZE", "").strip().upper()
    if env_size in _IMAGE_SIZES:
        return env_size

    cfg = _load_image_gen_config()
    gemini_cfg = cfg.get("gemini") if isinstance(cfg.get("gemini"), dict) else {}
    if isinstance(gemini_cfg, dict):
        value = gemini_cfg.get("image_size")
        if isinstance(value, str) and value.strip().upper() in _IMAGE_SIZES:
            return value.strip().upper()
    return DEFAULT_IMAGE_SIZE


def _extension_for_mime(mime_type: str) -> str:
    if not mime_type:
        return "png"
    if mime_type == "image/jpeg":
        return "jpg"
    ext = mimetypes.guess_extension(mime_type.split(";", 1)[0].strip())
    return (ext or ".png").lstrip(".")


def _extract_error_message(response: requests.Response) -> str:
    """Return a bounded provider error message without leaking request headers."""
    try:
        payload = response.json()
        err = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(err, dict):
            msg = err.get("message")
            if isinstance(msg, str) and msg.strip():
                return msg.strip()[:500]
    except Exception:
        pass
    return (response.text or response.reason or "unknown error")[:500]


class GeminiImageGenProvider(ImageGenProvider):
    """Google Gemini native image generation backend."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Gemini / Nano Banana"

    def is_available(self) -> bool:
        api_key, _ = _resolve_api_key()
        return bool(api_key)

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta.get("display", model_id),
                "speed": meta.get("speed", ""),
                "strengths": meta.get("strengths", ""),
                "price": meta.get("price", ""),
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Gemini / Nano Banana",
            "badge": "paid",
            "tag": "Native Google Gemini image generation; accepts GEMINI_API_KEY, GOOGLE_API_KEY, or Palmer's NANO_BANANA_API_KEY alias",
            "env_vars": [
                {
                    "key": "GEMINI_API_KEY",
                    "prompt": "Google Gemini API key",
                    "url": "https://aistudio.google.com/app/apikey",
                }
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="gemini",
                aspect_ratio=aspect,
            )

        api_key, key_name = _resolve_api_key()
        if not api_key:
            return error_response(
                error=(
                    "No Gemini API key configured. Set GEMINI_API_KEY or GOOGLE_API_KEY; "
                    "Palmer also accepts NANO_BANANA_API_KEY as a local alias."
                ),
                error_type="auth_required",
                provider="gemini",
                aspect_ratio=aspect,
                prompt=prompt,
            )

        model_id, _meta = _resolve_model()
        image_size = _resolve_image_size()
        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {
                    "aspectRatio": _ASPECT_RATIOS.get(aspect, "16:9"),
                    "imageSize": image_size,
                },
            },
        }
        url = f"{API_BASE_URL}/models/{model_id}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "Hermes-Agent-Gemini-ImageGen/1.0",
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=180)
        except requests.Timeout:
            return error_response(
                error="Gemini image generation timed out (180s)",
                error_type="timeout",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"Gemini connection error: {exc}",
                error_type="connection_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"Gemini request setup failed: {type(exc).__name__}: {exc}",
                error_type="request_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        if response.status_code >= 400:
            return error_response(
                error=(
                    f"Gemini image generation failed ({response.status_code}) using {key_name}: "
                    f"{_extract_error_message(response)}"
                ),
                error_type="api_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            result = response.json()
        except Exception as exc:
            return error_response(
                error=f"Gemini returned invalid JSON: {exc}",
                error_type="invalid_response",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        text_parts: List[str] = []
        image_parts: List[Tuple[str, str]] = []
        for candidate in result.get("candidates", []) if isinstance(result, dict) else []:
            content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
                inline = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline, dict):
                    data = inline.get("data")
                    mime_type = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    if isinstance(data, str) and data.strip():
                        image_parts.append((data.strip(), str(mime_type)))

        if not image_parts:
            finish_reasons = []
            for candidate in result.get("candidates", []) if isinstance(result, dict) else []:
                if isinstance(candidate, dict) and candidate.get("finishReason"):
                    finish_reasons.append(str(candidate.get("finishReason")))
            suffix = f" Finish reason: {', '.join(finish_reasons)}." if finish_reasons else ""
            return error_response(
                error=f"Gemini returned no inline image data.{suffix}",
                error_type="empty_response",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        b64_data, mime_type = image_parts[0]
        try:
            saved_path = save_b64_image(
                b64_data,
                prefix=f"gemini_{model_id.replace('/', '_')}",
                extension=_extension_for_mime(mime_type),
            )
        except Exception as exc:
            return error_response(
                error=f"Could not save Gemini image to cache: {exc}",
                error_type="io_error",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        return success_response(
            image=str(saved_path),
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="gemini",
            extra={
                "text": "\n".join(text_parts),
                "mime_type": mime_type,
                "image_size": image_size,
            },
        )


def register(ctx):
    """Plugin entry point — wire ``GeminiImageGenProvider`` into Hermes."""
    ctx.register_image_gen_provider(GeminiImageGenProvider())
