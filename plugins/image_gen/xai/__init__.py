"""xAI image generation backend.

Exposes xAI's ``grok-imagine-image`` model as an
:class:`ImageGenProvider` implementation.

Features:
- Text-to-image generation
- Multiple aspect ratios (1:1, 16:9, 9:16, etc.)
- Multiple resolutions (1K, 2K)
- Base64 output saved to cache

Selection precedence (first hit wins):
1. ``XAI_IMAGE_MODEL`` env var
2. ``image_gen.xai.model`` in ``config.yaml``
3. :data:`DEFAULT_MODEL`
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    save_url_image,
    success_response,
)
from tools.xai_http import hermes_xai_user_agent, resolve_xai_http_credentials

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

_MODELS: Dict[str, Dict[str, Any]] = {
    "grok-imagine-image": {
        "display": "Grok Imagine Image",
        "speed": "~5-10s",
        "strengths": "Fast, high-quality",
    },
    "grok-imagine-image-quality": {
        "display": "Grok Imagine Image (Quality)",
        "speed": "~10-20s",
        "strengths": "Higher fidelity / detail; slower than the standard model.",
    },
}

DEFAULT_MODEL = "grok-imagine-image"

# xAI aspect ratios (more options than FAL/OpenAI)
_XAI_ASPECT_RATIOS = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
    "4:3": "4:3",
    "3:4": "3:4",
    "3:2": "3:2",
    "2:3": "2:3",
}

# xAI resolutions
_XAI_RESOLUTIONS = {"1k", "2k"}

DEFAULT_RESOLUTION = "1k"

# Local-file extensions xAI's edits endpoint accepts, mapped to the MIME type
# used when inlining the file as a base64 data URI.
_IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


# ---------------------------------------------------------------------------
# Reference-image helpers (image-to-image via /v1/images/edits)
# ---------------------------------------------------------------------------


def _to_edit_image_entry(ref: str) -> Dict[str, str]:
    """Turn a user-supplied image reference into an xAI edits image entry.

    Remote URLs (``http(s)://``) and ``data:`` URIs pass through untouched.
    A local file path is read and inlined as a base64 ``data:`` URI — xAI's
    edits endpoint accepts data URIs directly, which avoids having to host
    the file on a public URL first (and sidesteps the NAS-returns-HTML
    gotcha that the video path has to work around).
    """
    value = (ref or "").strip()
    if not value:
        raise ValueError("empty image reference")
    if value.startswith(("http://", "https://", "data:")):
        return {"url": value}
    if not os.path.isfile(value):
        raise ValueError(f"reference image not found: {value}")
    ext = os.path.splitext(value)[1].lower()
    mime = _IMAGE_MIME.get(ext)
    if mime is None:
        raise ValueError(
            f"unsupported image type '{ext or '?'}' (use png, jpg, or webp)"
        )
    with open(value, "rb") as fh:
        encoded = base64.b64encode(fh.read()).decode("ascii")
    return {"url": f"data:{mime};base64,{encoded}"}


def _collect_input_images(
    image_url: Any,
    reference_image_urls: Any,
) -> List[str]:
    """Merge ``image_url`` and ``reference_image_urls`` into one ordered list.

    The primary ``image_url`` comes first, then any reference images. Empty
    / non-string entries are dropped. Mirrors the video tool's surface,
    which exposes both a primary drive image and a list of refs.
    """
    out: List[str] = []
    if isinstance(image_url, str) and image_url.strip():
        out.append(image_url.strip())
    if isinstance(reference_image_urls, str):
        reference_image_urls = [reference_image_urls]
    if isinstance(reference_image_urls, (list, tuple)):
        for item in reference_image_urls:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
    return out


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _load_xai_config() -> Dict[str, Any]:
    """Read ``image_gen.xai`` from config.yaml."""
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        xai_section = section.get("xai") if isinstance(section, dict) else None
        return xai_section if isinstance(xai_section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen.xai config: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    """Decide which model to use and return ``(model_id, meta)``."""
    env_override = os.environ.get("XAI_IMAGE_MODEL")
    if env_override and env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_xai_config()
    candidate = cfg.get("model") if isinstance(cfg.get("model"), str) else None
    if candidate and candidate in _MODELS:
        return candidate, _MODELS[candidate]

    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _resolve_resolution() -> str:
    """Get configured resolution."""
    cfg = _load_xai_config()
    res = cfg.get("resolution") if isinstance(cfg.get("resolution"), str) else None
    if res and res in _XAI_RESOLUTIONS:
        return res
    return DEFAULT_RESOLUTION


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class XAIImageGenProvider(ImageGenProvider):
    """xAI ``grok-imagine-image`` backend."""

    @property
    def name(self) -> str:
        return "xai"

    @property
    def display_name(self) -> str:
        return "xAI (Grok)"

    def is_available(self) -> bool:
        creds = resolve_xai_http_credentials()
        return bool(creds.get("api_key"))

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta.get("display", model_id),
                "speed": meta.get("speed", ""),
                "strengths": meta.get("strengths", ""),
            }
            for model_id, meta in _MODELS.items()
        ]

    def get_setup_schema(self) -> Dict[str, Any]:
        # Auth resolution is delegated to the shared ``xai_grok`` post_setup
        # hook (``hermes_cli/tools_config.py``); identical to the TTS / video
        # gen entries so users see the same OAuth-or-API-key choice for every
        # xAI service.
        return {
            "name": "xAI Grok Imagine (image)",
            "badge": "paid",
            "tag": "grok-imagine-image — text-to-image; uses xAI Grok OAuth or XAI_API_KEY",
            "env_vars": [],
            "post_setup": "xai_grok",
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        *,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Generate an image using xAI's grok-imagine-image.

        Text-to-image by default. When ``image_url`` and/or
        ``reference_image_urls`` are supplied, the call routes to xAI's
        ``/images/edits`` endpoint instead — using the input image(s) as a
        reference for image-to-image / character / style transfer. Inputs
        may be public URLs, ``data:`` URIs, or local file paths (inlined as
        base64). Single input uses the ``image`` field; multiple use the
        ``images`` array.
        """
        creds = resolve_xai_http_credentials()
        api_key = str(creds.get("api_key") or "").strip()
        provider_name = str(creds.get("provider") or "xai").strip() or "xai"
        if not api_key:
            return error_response(
                error="No xAI credentials found. Configure xAI OAuth in `hermes model` or set XAI_API_KEY.",
                error_type="missing_api_key",
                provider=provider_name,
                aspect_ratio=aspect_ratio,
            )

        model_id, meta = _resolve_model()
        aspect = resolve_aspect_ratio(aspect_ratio)
        xai_ar = _XAI_ASPECT_RATIOS.get(aspect, "1:1")
        resolution = _resolve_resolution()
        xai_res = resolution if resolution in _XAI_RESOLUTIONS else DEFAULT_RESOLUTION

        payload: Dict[str, Any] = {
            "model": model_id,
            "prompt": prompt,
            "aspect_ratio": xai_ar,
            "resolution": xai_res,
        }

        # Reference-image (image-to-image) path: route to /images/edits and
        # attach the input image(s). Text-to-image stays on /images/generations.
        input_refs = _collect_input_images(image_url, reference_image_urls)
        endpoint = "images/generations"
        if input_refs:
            try:
                entries = [_to_edit_image_entry(ref) for ref in input_refs]
            except Exception as exc:
                return error_response(
                    error=f"Invalid reference image: {exc}",
                    error_type="invalid_input",
                    provider=provider_name,
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            endpoint = "images/edits"
            if len(entries) == 1:
                payload["image"] = entries[0]
            else:
                payload["images"] = entries

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": hermes_xai_user_agent(),
        }

        base_url = str(creds.get("base_url") or "https://api.x.ai/v1").strip().rstrip("/")

        try:
            response = requests.post(
                f"{base_url}/{endpoint}",
                headers=headers,
                json=payload,
                timeout=180 if input_refs else 120,
            )
            response.raise_for_status()
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else 0
            try:
                err_msg = response.json().get("error", {}).get("message", response.text[:300])
            except Exception:
                err_msg = response.text[:300] if response is not None else str(exc)
            logger.error("xAI image gen failed (%d): %s", status, err_msg)
            return error_response(
                error=f"xAI image generation failed ({status}): {err_msg}",
                error_type="api_error",
                provider=provider_name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.Timeout:
            return error_response(
                error="xAI image generation timed out (120s)",
                error_type="timeout",
                provider=provider_name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"xAI connection error: {exc}",
                error_type="connection_error",
                provider=provider_name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            result = response.json()
        except Exception as exc:
            return error_response(
                error=f"xAI returned invalid JSON: {exc}",
                error_type="invalid_response",
                provider=provider_name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Parse response — xAI returns data[0].b64_json or data[0].url
        data = result.get("data", [])
        if not data:
            return error_response(
                error="xAI returned no image data",
                error_type="empty_response",
                provider=provider_name,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        first = data[0]
        b64 = first.get("b64_json")
        url = first.get("url")

        if b64:
            try:
                saved_path = save_b64_image(b64, prefix=f"xai_{model_id}")
            except Exception as exc:
                return error_response(
                    error=f"Could not save image to cache: {exc}",
                    error_type="io_error",
                    provider="xai",
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            image_ref = str(saved_path)
        elif url:
            # xAI's grok-imagine-image returns ephemeral ``imgen.x.ai/xai-tmp-*``
            # URLs that 404 within minutes — by the time Telegram's
            # ``send_photo`` or any downstream consumer fetches them, the
            # asset is gone (#26942).  Materialise the bytes locally at
            # tool-completion time so the gateway has a stable file path to
            # upload, mirroring the b64 branch above and the audio_cache
            # pattern used by text_to_speech.
            try:
                saved_path = save_url_image(url, prefix=f"xai_{model_id}")
            except Exception as exc:
                logger.warning(
                    "xAI image URL %s could not be cached (%s); falling back to bare URL.",
                    url,
                    exc,
                )
                image_ref = url
            else:
                image_ref = str(saved_path)
        else:
            return error_response(
                error="xAI response contained neither b64_json nor URL",
                error_type="empty_response",
                provider="xai",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        extra: Dict[str, Any] = {
            "resolution": xai_res,
        }
        if input_refs:
            extra["edited"] = True
            extra["input_images"] = len(input_refs)

        return success_response(
            image=image_ref,
            model=model_id,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="xai",
            extra=extra,
        )


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------


def register(ctx: Any) -> None:
    """Register this provider with the image gen registry."""
    ctx.register_image_gen_provider(XAIImageGenProvider())
