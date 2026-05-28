"""Google Gemini image generation backend.

Supports Gemini native image generation/editing via the Google AI Studio
``generateContent`` API. Input/reference images are sent as inlineData parts,
so the provider actually receives the pixels instead of relying on chat vision
context. Psychic remote APIs remain sadly unsupported.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

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

_MODELS: Dict[str, Dict[str, Any]] = {
    "gemini-2.5-flash-image": {
        "display": "Gemini 2.5 Flash Image",
        "speed": "fast",
        "strengths": "Low-cost image generation, edits, multi-reference composition",
        "price": "Google AI Studio pricing",
    },
    "gemini-3.1-flash-image-preview": {
        "display": "Gemini 3.1 Flash Image Preview",
        "speed": "fast",
        "strengths": "Newer preview image model; supports imageConfig controls",
        "price": "Google AI Studio pricing",
    },
    "gemini-3-pro-image-preview": {
        "display": "Gemini 3 Pro Image Preview",
        "speed": "slower",
        "strengths": "Higher-end preview image generation/editing",
        "price": "Google AI Studio pricing",
    },
}

DEFAULT_MODEL = "gemini-2.5-flash-image"
_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_MAX_INPUT_BYTES = 20 * 1024 * 1024

_GEMINI_ASPECT_RATIOS = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}

_MIME_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def _get_env_value(*keys: str) -> Optional[str]:
    """Read an env var, falling back to Hermes' .env loader."""
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    try:
        from hermes_cli.config import get_env_value

        for key in keys:
            value = get_env_value(key)
            if value:
                return value
    except Exception as exc:  # pragma: no cover - defensive only
        logger.debug("Could not read Gemini env value: %s", exc)
    return None


def _load_gemini_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        gemini = section.get("gemini") if isinstance(section, dict) else None
        return gemini if isinstance(gemini, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen.gemini config: %s", exc)
        return {}


def _resolve_model(explicit: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
    candidates = [
        explicit,
        os.environ.get("GEMINI_IMAGE_MODEL"),
        _load_gemini_config().get("model"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str):
            normalized = candidate.strip().removeprefix("models/")
            if normalized in _MODELS:
                return normalized, _MODELS[normalized]
    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _mime_from_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed and guessed.startswith("image/"):
        return guessed
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"


def _inline_part_from_source(source: str) -> Dict[str, Any]:
    """Convert a local path, URL, or data URI into a Gemini inlineData part."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("image source must be a non-empty string")
    value = source.strip()

    if value.startswith("data:"):
        header, _, payload = value.partition(",")
        if not payload or ";base64" not in header:
            raise ValueError("data URI image inputs must be base64-encoded")
        mime = header[5:].split(";", 1)[0] or "image/png"
        return {"inlineData": {"mimeType": mime, "data": payload}}

    if value.startswith(("http://", "https://")):
        response = requests.get(value, timeout=45, stream=True)
        response.raise_for_status()
        content_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if not content_type.startswith("image/"):
            raise ValueError(f"URL did not return an image content-type: {content_type or 'unknown'}")
        chunks: List[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > _MAX_INPUT_BYTES:
                raise ValueError("input image exceeds 20MB cap")
            chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise ValueError("input image URL returned 0 bytes")
        return {"inlineData": {"mimeType": content_type, "data": base64.b64encode(data).decode("ascii")}}

    path = Path(value).expanduser()
    if not path.exists() or not path.is_file():
        raise ValueError(f"input image path does not exist: {value}")
    data = path.read_bytes()
    if len(data) > _MAX_INPUT_BYTES:
        raise ValueError("input image exceeds 20MB cap")
    return {"inlineData": {"mimeType": _mime_from_path(path), "data": base64.b64encode(data).decode("ascii")}}


def _collect_image_sources(kwargs: Dict[str, Any]) -> List[str]:
    sources: List[str] = []
    for key in ("input_image", "image_url"):
        value = kwargs.get(key)
        if isinstance(value, str) and value.strip():
            sources.append(value.strip())
    refs = kwargs.get("reference_images") or kwargs.get("reference_image_urls")
    if isinstance(refs, str) and refs.strip():
        sources.append(refs.strip())
    elif isinstance(refs, list):
        for item in refs:
            if isinstance(item, str) and item.strip():
                sources.append(item.strip())
    return sources


class GeminiImageGenProvider(ImageGenProvider):
    """Google AI Studio Gemini image generation/editing backend."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    def is_available(self) -> bool:
        return bool(_get_env_value("GEMINI_API_KEY", "GOOGLE_API_KEY"))

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
            "name": "Google Gemini Image",
            "badge": "paid",
            "tag": "Gemini image generation/editing via Google AI Studio (GEMINI_API_KEY)",
            "env_vars": [
                {
                    "key": "GEMINI_API_KEY",
                    "prompt": "Google AI Studio / Gemini API key",
                    "url": "https://aistudio.google.com/app/apikey",
                },
            ],
        }

    def generate(self, prompt: str, aspect_ratio: str = DEFAULT_ASPECT_RATIO, **kwargs: Any) -> Dict[str, Any]:
        prompt = (prompt or "").strip()
        aspect = resolve_aspect_ratio(aspect_ratio)
        if not prompt:
            return error_response(
                error="Prompt is required and must be a non-empty string",
                error_type="invalid_argument",
                provider="gemini",
                aspect_ratio=aspect,
            )

        api_key = _get_env_value("GEMINI_API_KEY", "GOOGLE_API_KEY")
        if not api_key:
            return error_response(
                error="GEMINI_API_KEY or GOOGLE_API_KEY not set. Add the key to ~/.hermes/.env or run `hermes tools`.",
                error_type="auth_required",
                provider="gemini",
                aspect_ratio=aspect,
            )

        model_id, _meta = _resolve_model(kwargs.get("model") if isinstance(kwargs.get("model"), str) else None)
        image_sources = _collect_image_sources(kwargs)
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        try:
            for source in image_sources:
                parts.append(_inline_part_from_source(source))
        except Exception as exc:
            return error_response(
                error=f"Could not prepare input/reference image: {exc}",
                error_type="invalid_image_input",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        generation_config: Dict[str, Any] = {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": _GEMINI_ASPECT_RATIOS.get(aspect, "1:1")},
        }
        resolution = kwargs.get("resolution") or _load_gemini_config().get("resolution")
        if isinstance(resolution, str) and resolution.strip():
            generation_config["imageConfig"]["imageSize"] = resolution.strip()

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": generation_config,
        }
        url = _ENDPOINT.format(model=quote(model_id, safe=""))

        try:
            response = requests.post(
                url,
                params={"key": api_key},
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=180,
            )
            if response.status_code == 400 and "imageConfig" in response.text:
                # Older/preview models can lag the docs. Retry without imageConfig
                # instead of failing an otherwise valid prompt.
                payload["generationConfig"] = {"responseModalities": ["TEXT", "IMAGE"]}
                response = requests.post(
                    url,
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=180,
                )
            response.raise_for_status()
            result = response.json()
        except requests.Timeout:
            return error_response(
                error="Gemini image generation timed out (180s)",
                error_type="timeout",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            try:
                body = exc.response.json() if exc.response is not None else {}
                message = body.get("error", {}).get("message") or str(body)[:300]
            except Exception:
                message = exc.response.text[:300] if exc.response is not None else str(exc)
            return error_response(
                error=f"Gemini image generation failed ({status}): {message}",
                error_type="api_error",
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
                error=f"Gemini returned an invalid response: {exc}",
                error_type="invalid_response",
                provider="gemini",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        output_text: List[str] = []
        for candidate in result.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if part.get("text"):
                    output_text.append(part["text"])
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                    extension = _MIME_EXTENSIONS.get(str(mime).lower(), "png")
                    path = save_b64_image(inline["data"], prefix="gemini", extension=extension)
                    return success_response(
                        image=str(path),
                        model=model_id,
                        prompt=prompt,
                        aspect_ratio=aspect,
                        provider="gemini",
                        extra={
                            "mode": "edit" if image_sources else "generate",
                            "input_images": len(image_sources),
                            "text": "\n".join(output_text).strip(),
                        },
                    )

        return error_response(
            error="Gemini returned no inline image data",
            error_type="empty_response",
            provider="gemini",
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
        )


def register(ctx):
    ctx.register_image_gen_provider(GeminiImageGenProvider())
