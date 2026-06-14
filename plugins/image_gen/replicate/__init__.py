"""Replicate image generation backend.

Self-contained :class:`ImageGenProvider` that drives Replicate's HTTP API
directly (no SDK dependency). Runs a prediction synchronously via the
``Prefer: wait`` header and falls back to polling for slower models.

Default model is ``black-forest-labs/flux-1.1-pro-ultra`` — Replicate's
flagship FLUX image model (up to 4MP, photoreal). Override the active
model with:

    1. ``REPLICATE_IMAGE_MODEL`` env var
    2. ``image_gen.replicate.model`` in ``config.yaml``
    3. ``DEFAULT_MODEL`` below

Authentication via ``REPLICATE_API_TOKEN``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    save_url_image,
    success_response,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.replicate.com/v1"
DEFAULT_MODEL = "black-forest-labs/flux-1.1-pro-ultra"

# Hermes aspect-ratio vocabulary -> Replicate-native ratios accepted by the
# default FLUX model (and most other Replicate image models).
_ASPECT_MAP = {
    "landscape": "16:9",
    "square": "1:1",
    "portrait": "9:16",
}

# Per-model curated metadata for the `hermes tools` picker. Only the few
# headline models — any Replicate `owner/name` still works via override.
_MODELS: List[Dict[str, Any]] = [
    {
        "id": "black-forest-labs/flux-1.1-pro-ultra",
        "display": "FLUX 1.1 Pro Ultra",
        "speed": "~10s",
        "strengths": "Flagship FLUX. Up to 4MP, photoreal, strong prompt adherence.",
        "price": "~$0.06/image",
    },
    {
        "id": "google/imagen-4-ultra",
        "display": "Imagen 4 Ultra",
        "speed": "~15s",
        "strengths": "Google's top image model. Excellent text rendering.",
        "price": "~$0.06/image",
    },
    {
        "id": "bytedance/seedream-4",
        "display": "Seedream 4",
        "speed": "~10s",
        "strengths": "Very popular all-rounder, multi-image support.",
        "price": "~$0.03/image",
    },
    {
        "id": "recraft-ai/recraft-v3",
        "display": "Recraft V3",
        "speed": "~10s",
        "strengths": "Best-in-class for vector/branding/typography.",
        "price": "~$0.04/image",
    },
]


def _api_token() -> str:
    return (os.getenv("REPLICATE_API_TOKEN", "") or "").strip()


def _resolve_model() -> str:
    env = (os.getenv("REPLICATE_IMAGE_MODEL", "") or "").strip()
    if env:
        return env
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        ig = cfg.get("image_gen") if isinstance(cfg, dict) else None
        rep = (ig or {}).get("replicate") if isinstance(ig, dict) else None
        model = (rep or {}).get("model") if isinstance(rep, dict) else None
        if isinstance(model, str) and model.strip():
            return model.strip()
    except Exception:  # noqa: BLE001 — config is best-effort
        pass
    return DEFAULT_MODEL


def _extract_image_url(output: Any) -> Optional[str]:
    """Replicate image output is a URL string or a list of URL strings."""
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            return first
    if isinstance(output, dict):
        for key in ("image", "url", "output"):
            v = output.get(key)
            if isinstance(v, str):
                return v
    return None


def _run_prediction(
    model: str, payload: Dict[str, Any], *, timeout_s: float = 180.0
) -> Dict[str, Any]:
    """Create a prediction (synchronous via Prefer: wait) and poll to terminal."""
    token = _api_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    url = f"{API_BASE}/models/{model}/predictions"
    resp = requests.post(url, headers=headers, json={"input": payload}, timeout=90)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Replicate HTTP {resp.status_code}: {resp.text[:300]}")
    pred = resp.json()

    deadline = time.monotonic() + timeout_s
    get_url = (pred.get("urls") or {}).get("get")
    while pred.get("status") in ("starting", "processing"):
        if time.monotonic() > deadline:
            raise TimeoutError(f"Replicate prediction timed out after {timeout_s:.0f}s")
        if not get_url:
            break
        time.sleep(2.5)
        pr = requests.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if pr.status_code != 200:
            raise RuntimeError(f"Replicate poll HTTP {pr.status_code}: {pr.text[:200]}")
        pred = pr.json()

    if pred.get("status") != "succeeded":
        raise RuntimeError(
            f"Replicate prediction {pred.get('status')}: {pred.get('error') or 'no output'}"
        )
    return pred


class ReplicateImageGenProvider(ImageGenProvider):
    """Replicate image generation backend."""

    @property
    def name(self) -> str:
        return "replicate"

    @property
    def display_name(self) -> str:
        return "Replicate"

    def is_available(self) -> bool:
        return bool(_api_token())

    def list_models(self) -> List[Dict[str, Any]]:
        return list(_MODELS)

    def default_model(self) -> Optional[str]:
        return _resolve_model()

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Replicate",
            "badge": "paid",
            "tag": "FLUX 1.1 Pro Ultra, Imagen 4, Seedream 4, Recraft — any Replicate model.",
            "env_vars": [
                {
                    "key": "REPLICATE_API_TOKEN",
                    "prompt": "Replicate API token",
                    "url": "https://replicate.com/account/api-tokens",
                },
            ],
        }

    def generate(
        self,
        prompt: str,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        aspect = resolve_aspect_ratio(aspect_ratio)
        model = _resolve_model()

        if not _api_token():
            return error_response(
                error="REPLICATE_API_TOKEN is not set.",
                error_type="missing_credentials",
                provider="replicate",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        payload: Dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": _ASPECT_MAP.get(aspect, "16:9"),
        }
        # Most Replicate image models accept output_format; harmless extras
        # are ignored by models that don't declare them.
        fmt = kwargs.get("output_format")
        payload["output_format"] = fmt if fmt in ("png", "jpg", "webp") else "png"
        if isinstance(kwargs.get("seed"), int):
            payload["seed"] = kwargs["seed"]

        try:
            pred = _run_prediction(model, payload)
        except Exception as exc:  # noqa: BLE001 — never raise out of generate
            logger.warning("Replicate image generation failed: %s", exc, exc_info=True)
            return error_response(
                error=f"Replicate image generation failed: {exc}",
                error_type=type(exc).__name__,
                provider="replicate",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        image_url = _extract_image_url(pred.get("output"))
        if not image_url:
            return error_response(
                error="Replicate returned no image URL.",
                error_type="provider_contract",
                provider="replicate",
                model=model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Materialise locally — Replicate delivery URLs are ephemeral.
        image_ref = image_url
        try:
            image_ref = str(save_url_image(image_url, prefix="replicate"))
        except Exception as exc:  # noqa: BLE001 — fall back to the bare URL
            logger.warning("Replicate image download failed (%s); returning URL", exc)

        return success_response(
            image=image_ref,
            model=model,
            prompt=prompt,
            aspect_ratio=aspect,
            provider="replicate",
        )


def register(ctx) -> None:
    """Plugin entry point — wire ``ReplicateImageGenProvider`` into the registry."""
    ctx.register_image_gen_provider(ReplicateImageGenProvider())
