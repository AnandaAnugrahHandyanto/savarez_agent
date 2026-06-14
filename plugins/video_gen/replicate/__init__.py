"""Replicate video generation backend.

Self-contained :class:`VideoGenProvider` that drives Replicate's HTTP API
directly (no SDK dependency). Submits a prediction and polls to terminal
state (video models routinely exceed the synchronous ``Prefer: wait``
window).

Default model is ``google/veo-3.1`` — Google's flagship video model with
native audio, supporting both text-to-video and image-to-video (the
``image`` input routes to i2v). Override the active model with:

    1. ``model=`` arg on the tool call
    2. ``REPLICATE_VIDEO_MODEL`` env var
    3. ``video_gen.replicate.model`` in ``config.yaml``
    4. ``DEFAULT_MODEL`` below

Authentication via ``REPLICATE_API_TOKEN``.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from agent.video_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    DEFAULT_RESOLUTION,
    VideoGenProvider,
    error_response,
    save_bytes_video,
    success_response,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.replicate.com/v1"
DEFAULT_MODEL = "google/veo-3.1"

_MODELS: List[Dict[str, Any]] = [
    {
        "id": "google/veo-3.1",
        "display": "Veo 3.1",
        "speed": "~1-3min",
        "strengths": "SOTA quality, native audio, text-to-video + image-to-video.",
        "price": "~$0.40/s",
        "modalities": ["text", "image"],
    },
    {
        "id": "kwaivgi/kling-v2.5-turbo-pro",
        "display": "Kling v2.5 Turbo Pro",
        "speed": "~1-2min",
        "strengths": "Excellent motion & dynamics, strong image-to-video.",
        "price": "~$0.25/run",
        "modalities": ["text", "image"],
    },
    {
        "id": "bytedance/seedance-1-pro",
        "display": "Seedance 1 Pro",
        "speed": "~1min",
        "strengths": "Fast, cinematic, good value.",
        "price": "~$0.15/run",
        "modalities": ["text", "image"],
    },
]


def _api_token() -> str:
    return (os.getenv("REPLICATE_API_TOKEN", "") or "").strip()


def _resolve_model(explicit: Optional[str] = None) -> str:
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    env = (os.getenv("REPLICATE_VIDEO_MODEL", "") or "").strip()
    if env:
        return env
    try:
        from hermes_cli.config import load_config

        cfg = load_config() or {}
        vg = cfg.get("video_gen") if isinstance(cfg, dict) else None
        rep = (vg or {}).get("replicate") if isinstance(vg, dict) else None
        model = (rep or {}).get("model") if isinstance(rep, dict) else None
        if isinstance(model, str) and model.strip():
            return model.strip()
    except Exception:  # noqa: BLE001 — config is best-effort
        pass
    return DEFAULT_MODEL


def _extract_video_url(output: Any) -> Optional[str]:
    if isinstance(output, str):
        return output
    if isinstance(output, list) and output:
        last = output[-1]
        if isinstance(last, str):
            return last
    if isinstance(output, dict):
        for key in ("video", "url", "output"):
            v = output.get(key)
            if isinstance(v, str):
                return v
    return None


def _run_prediction(
    model: str, payload: Dict[str, Any], *, timeout_s: float = 600.0
) -> Dict[str, Any]:
    """Create a prediction and poll to terminal state."""
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
        time.sleep(5)
        pr = requests.get(get_url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
        if pr.status_code != 200:
            raise RuntimeError(f"Replicate poll HTTP {pr.status_code}: {pr.text[:200]}")
        pred = pr.json()

    if pred.get("status") != "succeeded":
        raise RuntimeError(
            f"Replicate prediction {pred.get('status')}: {pred.get('error') or 'no output'}"
        )
    return pred


class ReplicateVideoGenProvider(VideoGenProvider):
    """Replicate video generation backend."""

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

    def capabilities(self) -> Dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "aspect_ratios": ["16:9", "9:16"],
            "resolutions": ["720p", "1080p"],
            "max_duration": 8,
            "min_duration": 4,
            "supports_audio": True,
            "supports_negative_prompt": True,
            "max_reference_images": 3,
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Replicate",
            "badge": "paid",
            "tag": "Veo 3.1, Kling v2.5, Seedance — any Replicate video model.",
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
        *,
        model: Optional[str] = None,
        image_url: Optional[str] = None,
        reference_image_urls: Optional[List[str]] = None,
        duration: Optional[int] = None,
        aspect_ratio: str = DEFAULT_ASPECT_RATIO,
        resolution: str = DEFAULT_RESOLUTION,
        negative_prompt: Optional[str] = None,
        audio: Optional[bool] = None,
        seed: Optional[int] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        active_model = _resolve_model(model)
        modality = "image" if image_url else "text"
        aspect = aspect_ratio if aspect_ratio in ("16:9", "9:16") else "16:9"

        if not _api_token():
            return error_response(
                error="REPLICATE_API_TOKEN is not set.",
                error_type="missing_credentials",
                provider="replicate",
                model=active_model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        payload: Dict[str, Any] = {"prompt": prompt, "aspect_ratio": aspect}
        # resolution: Veo accepts 720p / 1080p.
        payload["resolution"] = resolution if resolution in ("720p", "1080p") else "720p"
        if isinstance(duration, int) and duration > 0:
            payload["duration"] = duration
        if image_url:
            payload["image"] = image_url
        if reference_image_urls:
            payload["reference_images"] = reference_image_urls
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if audio is not None:
            payload["generate_audio"] = bool(audio)
        if isinstance(seed, int):
            payload["seed"] = seed

        try:
            pred = _run_prediction(active_model, payload)
        except Exception as exc:  # noqa: BLE001 — never raise out of generate
            logger.warning("Replicate video generation failed: %s", exc, exc_info=True)
            return error_response(
                error=f"Replicate video generation failed: {exc}",
                error_type=type(exc).__name__,
                provider="replicate",
                model=active_model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        video_url = _extract_video_url(pred.get("output"))
        if not video_url:
            return error_response(
                error="Replicate returned no video URL.",
                error_type="provider_contract",
                provider="replicate",
                model=active_model,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        # Materialise locally — Replicate delivery URLs are ephemeral.
        video_ref = video_url
        try:
            r = requests.get(video_url, timeout=180)
            r.raise_for_status()
            video_ref = str(save_bytes_video(r.content, prefix="replicate"))
        except Exception as exc:  # noqa: BLE001 — fall back to the bare URL
            logger.warning("Replicate video download failed (%s); returning URL", exc)

        return success_response(
            video=video_ref,
            model=active_model,
            prompt=prompt,
            modality=modality,
            aspect_ratio=aspect,
            duration=int(duration) if isinstance(duration, int) else 0,
            provider="replicate",
        )


def register(ctx) -> None:
    """Plugin entry point — wire ``ReplicateVideoGenProvider`` into the registry."""
    ctx.register_video_gen_provider(ReplicateVideoGenProvider())
