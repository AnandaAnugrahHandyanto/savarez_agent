"""Pika Labs video generation backend.

User-facing surface: pick a **model** (``pika-2.0`` or ``pika-1.5``).
The plugin routes to Pika's REST API endpoint for both text-to-video and
image-to-video generation.

Model tiers:
  pika-2.0  — Latest model, best quality and prompt adherence
  pika-1.5  — Stable, fast generation

Selection precedence:
    1. ``model=`` arg from the tool call
    2. ``PIKA_VIDEO_MODEL`` env var
    3. ``video_gen.pika.model`` in ``config.yaml``
    4. ``video_gen.model`` in ``config.yaml`` (when it's one of our IDs)
    5. ``DEFAULT_MODEL`` (pika-2.0)

Authentication via ``PIKA_API_KEY`` (Bearer token). Output is an HTTPS URL
from Pika's CDN; the gateway downloads and delivers it.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from agent.video_gen_provider import (
    COMMON_ASPECT_RATIOS,
    COMMON_RESOLUTIONS,
    DEFAULT_ASPECT_RATIO,
    DEFAULT_RESOLUTION,
    VideoGenProvider,
    error_response,
    success_response,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model catalog
# ---------------------------------------------------------------------------

PIKA_MODELS: Dict[str, Dict[str, Any]] = {
    "pika-2.0": {
        "display": "Pika 2.0",
        "model_id": "pika-2.0",
        "speed": "~1-3 min",
        "price": "$0.12/s",
        "strengths": "Latest model, superior animation quality",
        "modalities": ["text", "image"],
    },
    "pika-1.5": {
        "display": "Pika 1.5",
        "model_id": "pika-1.5",
        "speed": "~1-2 min",
        "price": "$0.06/s",
        "strengths": "Fast, reliable, good for iteration",
        "modalities": ["text", "image"],
    },
}

DEFAULT_MODEL = "pika-2.0"


class PikaProvider(VideoGenProvider):
    """Pika Labs video generation backend."""

    @property
    def name(self) -> str:
        return "pika"

    @property
    def display_name(self) -> str:
        return "Pika Labs"

    def is_available(self) -> bool:
        return bool(os.environ.get("PIKA_API_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for mid, meta in PIKA_MODELS.items():
            out.append({
                "id": mid,
                "display": meta["display"],
                "speed": meta["speed"],
                "strengths": meta["strengths"],
                "price": meta["price"],
                "modalities": meta["modalities"],
            })
        return out

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def capabilities(self) -> Dict[str, Any]:
        return {
            "modalities": ["text", "image"],
            "aspect_ratios": list(COMMON_ASPECT_RATIOS),
            "resolutions": list(COMMON_RESOLUTIONS),
            "min_duration": 3,
            "max_duration": 15,
            "supports_audio": True,
            "supports_negative_prompt": True,
            "max_reference_images": 0,
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Pika Labs",
            "badge": "paid",
            "tag": "Animation-focused text-to-video and image-to-video",
            "env_vars": [
                {
                    "key": "PIKA_API_KEY",
                    "prompt": "Pika Labs API key",
                    "url": "https://pika.art/settings/api",
                },
            ],
        }

    # -----------------------------------------------------------------------
    # Model resolution
    # -----------------------------------------------------------------------

    def _resolve_model(self, model: Optional[str]) -> str:
        if model and model in PIKA_MODELS:
            return model
        env_model = os.environ.get("PIKA_VIDEO_MODEL")
        if env_model and env_model in PIKA_MODELS:
            return env_model
        try:
            from hermes_cli.config import load_config
            cfg = load_config()
            pika_cfg = (cfg or {}).get("video_gen", {}).get("pika", {})
            if isinstance(pika_cfg, dict):
                config_model = pika_cfg.get("model")
                if isinstance(config_model, str) and config_model in PIKA_MODELS:
                    return config_model
                generic = (cfg or {}).get("video_gen", {}).get("model")
                if isinstance(generic, str) and generic in PIKA_MODELS:
                    return generic
        except Exception:
            pass
        return DEFAULT_MODEL

    # -----------------------------------------------------------------------
    # Generation
    # -----------------------------------------------------------------------

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
        resolved_model = self._resolve_model(model)

        # Clamp duration: Pika supports 3-15s
        if duration is None:
            duration = 5
        duration = max(3, min(15, duration))

        api_key = os.environ.get("PIKA_API_KEY")
        if not api_key:
            return error_response(
                error="PIKA_API_KEY not set. Set it via `hermes tools` → Video Generation.",
                error_type="missing_api_key",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )

        # Build payload — Pika uses a unified /generate endpoint
        payload: Dict[str, Any] = {
            "prompt": prompt.strip(),
            "model": resolved_model,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
        }

        modality_used = "text"
        if image_url and image_url.strip():
            payload["image_url"] = image_url.strip()
            modality_used = "image"

        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if audio is not None:
            payload["audio"] = audio
        if seed is not None:
            payload["seed"] = seed

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            return self._submit_and_poll(
                payload=payload,
                headers=headers,
                resolved_model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration=duration,
                modality=modality_used,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Pika API request failed: %s", exc)
            return error_response(
                error=f"Pika API error: {exc}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )
        except Exception as exc:
            logger.error("Pika generation failed: %s", exc)
            return error_response(
                error=f"Generation error: {exc}",
                error_type="generation_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )

    def _submit_and_poll(
        self,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        resolved_model: str,
        prompt: str,
        aspect_ratio: str,
        duration: int,
        modality: str,
    ) -> Dict[str, Any]:
        """Submit generation job and poll until complete."""
        submit_url = "https://api.pika.art/v1/generate"
        logger.info("Submitting Pika generation: %s", payload.get("prompt", "")[:80])

        resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Submit failed: HTTP {resp.status_code} — {resp.text}")

        job_data = resp.json()
        task_id = job_data.get("id") or job_data.get("task_id")
        if not task_id:
            raise RuntimeError(f"No task_id in response: {job_data}")

        logger.info("Pika task submitted: %s", task_id)

        max_wait = 600
        poll_interval = 10
        elapsed = 0

        status_url = f"https://api.pika.art/v1/tasks/{task_id}"

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_resp = requests.get(status_url, headers=headers, timeout=15)
            if status_resp.status_code != 200:
                raise RuntimeError(f"Status check failed: HTTP {status_resp.status_code}")

            status_data = status_resp.json()
            state = status_data.get("state", status_data.get("status", "")).lower()

            if state in ("completed", "finished", "succeeded", "done"):
                video_url = status_data.get("video_url") or status_data.get("result", {}).get("video_url")
                if video_url:
                    return success_response(
                        video=video_url,
                        model=resolved_model,
                        prompt=prompt,
                        modality=modality,
                        aspect_ratio=aspect_ratio,
                        duration=duration,
                        provider=self.name,
                    )
                raise RuntimeError(f"No video URL in completed job: {status_data}")

            elif state in ("failed", "error"):
                error_msg = status_data.get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Generation failed: {error_msg}")

            logger.info(
                "Pika generation in progress: %s%% (%ds elapsed)",
                status_data.get("progress", status_data.get("percent_complete", "?")),
                elapsed,
            )

        return error_response(
            error=f"Pika generation timed out after {max_wait}s. Task ID: {task_id}",
            error_type="timeout",
            provider=self.name,
            model=resolved_model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )


def register(ctx) -> None:
    """Register the Pika Labs video generation provider."""
    ctx.register_video_gen_provider(PikaProvider())
