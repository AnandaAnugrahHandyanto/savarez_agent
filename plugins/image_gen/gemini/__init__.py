"""Google Gemini image generation backend (AI Studio API).

Calls ``generativelanguage.googleapis.com/v1beta/models/{model}:generateContent``
with ``responseModalities=["IMAGE"]`` and decodes the returned ``inlineData``
part. The API key is resolved in this order:

1. ``GEMINI_API_KEY`` env (escape hatch for tests/scripts)
2. ``GOOGLE_API_KEY`` env (alternate official name)
3. Hermes auth store (provider ``gemini``) — same key used for text inference

Model selection (first hit wins):

1. ``GEMINI_IMAGE_MODEL`` env var
2. ``image_gen.gemini.model`` in config.yaml
3. ``image_gen.model`` (top-level) when it looks like a Gemini image model
4. :data:`DEFAULT_MODEL` — currently the most capable widely-available
   image-gen model. Override via config if Google has shipped a newer one.

Aspect ratio is passed via ``generationConfig.imageConfig.aspectRatio`` —
square/landscape/portrait → 1:1 / 16:9 / 9:16. If a future API version
rejects ``imageConfig``, the plugin retries once without it before
surfacing the error.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_b64_image,
    success_response,
)

logger = logging.getLogger(__name__)


DEFAULT_MODEL = "gemini-3-pro-image-preview"

_KNOWN_MODELS: Dict[str, Dict[str, Any]] = {
    "gemini-3-pro-image-preview": {
        "display": "Gemini 3 Pro Image (Nano Banana 2)",
        "speed": "~25s",
        "strengths": "Highest fidelity Nano Banana family; best prompt adherence",
    },
    "gemini-2.5-flash-image-preview": {
        "display": "Gemini 2.5 Flash Image (Nano Banana 1)",
        "speed": "~10s",
        "strengths": "Fast, cheap; good for iteration",
    },
}

_ASPECT_TO_RATIO = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}


def _load_image_gen_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        return section if isinstance(section, dict) else {}
    except Exception as exc:
        logger.debug("Could not load image_gen config: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    env_override = os.environ.get("GEMINI_IMAGE_MODEL", "").strip()
    if env_override:
        return env_override, _KNOWN_MODELS.get(env_override, {})

    cfg = _load_image_gen_config()
    sub = cfg.get("gemini") if isinstance(cfg.get("gemini"), dict) else {}
    if isinstance(sub, dict):
        v = (sub.get("model") or "").strip()
        if v:
            return v, _KNOWN_MODELS.get(v, {})

    top = (cfg.get("model") or "").strip()
    if top.startswith("gemini-") and "image" in top:
        return top, _KNOWN_MODELS.get(top, {})

    return DEFAULT_MODEL, _KNOWN_MODELS.get(DEFAULT_MODEL, {})


def _resolve_api_key() -> Optional[str]:
    for env_var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        v = (os.environ.get(env_var) or "").strip()
        if v:
            return v
    try:
        from hermes_cli.auth import resolve_api_key_provider_credentials

        creds = resolve_api_key_provider_credentials("gemini") or {}
        v = (creds.get("api_key") or "").strip()
        return v or None
    except Exception as exc:
        logger.debug("Could not resolve gemini key from auth store: %s", exc)
        return None


def _resolve_base_url() -> str:
    try:
        from hermes_cli.auth import resolve_api_key_provider_credentials

        creds = resolve_api_key_provider_credentials("gemini") or {}
        b = (creds.get("base_url") or "").strip().rstrip("/")
        if b:
            return b
    except Exception:
        pass
    return "https://generativelanguage.googleapis.com/v1beta"


def _post_generate_content(
    *,
    base_url: str,
    model: str,
    api_key: str,
    body: Dict[str, Any],
    timeout: float = 120.0,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """POST to generateContent. Returns (response_json, error_str)."""
    import httpx

    url = f"{base_url}/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key,
                },
                json=body,
            )
    except httpx.HTTPError as exc:
        return None, f"network error: {exc}"

    if r.status_code >= 400:
        snippet = r.text[:500] if r.text else f"HTTP {r.status_code}"
        return None, f"HTTP {r.status_code}: {snippet}"
    try:
        return r.json(), None
    except Exception as exc:
        return None, f"could not parse response JSON: {exc}"


def _extract_image_b64(payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """Return (b64_data, mime) from the first inline_data part, or (None, None)."""
    candidates = payload.get("candidates") or []
    for cand in candidates:
        parts = (cand.get("content") or {}).get("parts") or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if isinstance(inline, dict):
                data = inline.get("data")
                mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                if isinstance(data, str) and data:
                    return data, mime
    return None, None


class GeminiImageGenProvider(ImageGenProvider):
    """Google Gemini ``generateContent`` backend with image modality."""

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def display_name(self) -> str:
        return "Google Gemini"

    def is_available(self) -> bool:
        return bool(_resolve_api_key())

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {"id": mid, "display": m["display"], "speed": m["speed"],
             "strengths": m["strengths"], "price": "varies"}
            for mid, m in _KNOWN_MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Google Gemini",
            "badge": "paid (AI Studio)",
            "tag": "Nano Banana family — image_gen.gemini.model picks the variant",
            "env_vars": [
                {"key": "GEMINI_API_KEY",
                 "prompt": "Google AI Studio API key (or use existing 'gemini' auth)",
                 "url": "https://aistudio.google.com/apikey"},
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

        api_key = _resolve_api_key()
        if not api_key:
            return error_response(
                error=("No Gemini API key available. Set GEMINI_API_KEY in env, "
                       "or run `hermes auth add gemini --type api-key`."),
                error_type="auth_required",
                provider="gemini",
                aspect_ratio=aspect,
            )

        model, _meta = _resolve_model()
        base_url = _resolve_base_url()
        ratio = _ASPECT_TO_RATIO.get(aspect, "1:1")

        body: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": ratio},
            },
        }

        payload, err = _post_generate_content(
            base_url=base_url, model=model, api_key=api_key, body=body)

        if err and "imageConfig" in (err or "") and "400" in (err or ""):
            # Older Gemini image models reject imageConfig — retry without.
            logger.debug("Retrying gemini image gen without imageConfig: %s", err)
            body["generationConfig"].pop("imageConfig", None)
            payload, err = _post_generate_content(
                base_url=base_url, model=model, api_key=api_key, body=body)

        if err:
            classification = "rate_limited" if "429" in err else "api_error"
            if "401" in err or "403" in err or "PERMISSION_DENIED" in err:
                classification = "auth_required"
            return error_response(
                error=f"Gemini image generation failed: {err}",
                error_type=classification,
                provider="gemini",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        b64, mime = _extract_image_b64(payload or {})
        if not b64:
            block_reason = ((payload or {}).get("promptFeedback") or {}).get("blockReason")
            if block_reason:
                return error_response(
                    error=f"Gemini blocked the prompt: {block_reason}",
                    error_type="content_filter",
                    provider="gemini",
                    model=model,
                    prompt=prompt,
                    aspect_ratio=aspect,
                )
            return error_response(
                error="Gemini response contained no inline image data",
                error_type="empty_response",
                provider="gemini",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            ext = "png" if "png" in (mime or "") else ("jpg" if "jpeg" in (mime or "") else "png")
            saved_path = save_b64_image(b64, prefix=f"gemini_{model}", extension=ext)
        except TypeError:
            saved_path = save_b64_image(b64, prefix=f"gemini_{model}")
        except Exception as exc:
            return error_response(
                error=f"Could not save image to cache: {exc}",
                error_type="io_error",
                provider="gemini",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        return success_response(
            image=str(saved_path),
            model=model,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="gemini",
            extra={"aspect_ratio_param": ratio, "mime": mime or "image/png"},
        )


def register(ctx) -> None:
    ctx.register_image_gen_provider(GeminiImageGenProvider())
