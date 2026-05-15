"""Luma Dream Machine video generation backend.

User-facing surface: pick a **model** (``dream-machine-1.6`` or ``photon-1``).
The plugin auto-routes to Luma's ``/v1/generations/image`` (image-to-video)
or ``/v1/generations/text`` (text-to-video) endpoints.

Model tiers:
  dream-machine-1.6  — Photorealistic, best quality
  photon-1           — Fast generation, good for iteration

Selection precedence:
    1. ``model=`` arg from the tool call
    2. ``LUMA_VIDEO_MODEL`` env var
    3. ``video_gen.luma.model`` in ``config.yaml``
    4. ``video_gen.model`` in ``config.yaml`` (when it's one of our IDs)
    5. ``DEFAULT_MODEL`` (dream-machine-1.6)

Authentication via ``LUMA_API_KEY`` (Bearer token). Output is an HTTPS URL
from Luma's CDN; the gateway downloads and delivers it.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from agent.video_gen_provider import (
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

LUMA_MODELS: Dict[str, Dict[str, Any]] = {
    "dream-machine-1.6": {
        "display": "Dream Machine 1.6",
        "model_id": "dream-machine-1.6",
        "speed": "~2-5 min",
        "price": "$0.15/s",
        "strengths": "Photorealistic quality, cinematic results",
        "modalities": ["text", "image"],
    },
    "photon-1": {
        "display": "Photon 1.0",
        "model_id": "photon-1",
        "speed": "~1-2 min",
        "price": "$0.08/s",
        "strengths": "Fast generation, good for iteration",
        "modalities": ["text", "image"],
    },
}

DEFAULT_MODEL = "dream-machine-1.6"
SUPPORTED_ASPECT_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4")


class LumaProvider(VideoGenProvider):
    """Luma Dream Machine backend."""

    @property
    def name(self) -> str:
        return "luma"

    @property
    def display_name(self) -> str:
        return "Luma Dream Machine"

    def is_available(self) -> bool:
        return bool(os.environ.get("LUMA_API_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for mid, meta in LUMA_MODELS.items():
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
            "aspect_ratios": list(SUPPORTED_ASPECT_RATIOS),
            "resolutions": list(COMMON_RESOLUTIONS),
            "min_duration": 5,
            "max_duration": 10,
            "supports_audio": False,
            "supports_negative_prompt": False,
            "max_reference_images": 0,
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Luma Dream Machine",
            "badge": "paid",
            "tag": "Photorealistic text-to-video and image-to-video",
            "env_vars": [
                {
                    "key": "LUMA_API_KEY",
                    "prompt": "Luma AI API key",
                    "url": "https://lumalabs.ai/dream-machine/api",
                },
            ],
        }

    # -----------------------------------------------------------------------
    # Model resolution
    # -----------------------------------------------------------------------

    def _resolve_model(self, model: Optional[str]) -> str:
        if model and model in LUMA_MODELS:
            return model
        env_model = os.environ.get("LUMA_VIDEO_MODEL")
        if env_model and env_model in LUMA_MODELS:
            return env_model
        try:
            from hermes_cli.config import load_config
            cfg = load_config()
            luma_cfg = (cfg or {}).get("video_gen", {}).get("luma", {})
            if isinstance(luma_cfg, dict):
                config_model = luma_cfg.get("model")
                if isinstance(config_model, str) and config_model in LUMA_MODELS:
                    return config_model
                generic = (cfg or {}).get("video_gen", {}).get("model")
                if isinstance(generic, str) and generic in LUMA_MODELS:
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

        # Clamp aspect ratio
        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            aspect_ratio = DEFAULT_ASPECT_RATIO

        # Clamp duration: Luma supports 5 or 10
        if duration is None:
            duration = 5
        elif duration <= 5:
            duration = 5
        else:
            duration = 10

        api_key = os.environ.get("LUMA_API_KEY")
        if not api_key:
            return error_response(
                error="LUMA_API_KEY not set. Set it via `hermes tools` → Video Generation.",
                error_type="missing_api_key",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )

        # Choose endpoint based on modality
        if image_url and image_url.strip():
            endpoint = "https://api.lumalabs.ai/dream-machine/v1/generations/image"
            modality_used = "image"
            payload = {
                "prompt": prompt.strip(),
                "image_url": image_url.strip(),
                "aspect_ratio": aspect_ratio,
            }
        else:
            endpoint = "https://api.lumalabs.ai/dream-machine/v1/generations/text"
            modality_used = "text"
            payload = {
                "prompt": prompt.strip(),
                "aspect_ratio": aspect_ratio,
            }

        if seed is not None:
            payload["seed"] = seed

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Api-Key": api_key,
        }

        try:
            return self._submit_and_poll(
                endpoint=endpoint,
                payload=payload,
                headers=headers,
                resolved_model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration=duration,
                modality=modality_used,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Luma API request failed: %s", exc)
            return error_response(
                error=f"Luma API error: {exc}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )
        except Exception as exc:
            logger.error("Luma generation failed: %s", exc)
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
        endpoint: str,
        payload: Dict[str, Any],
        headers: Dict[str, str],
        resolved_model: str,
        prompt: str,
        aspect_ratio: str,
        duration: int,
        modality: str,
    ) -> Dict[str, Any]:
        """Submit generation job and poll until complete."""
        logger.info("Submitting Luma generation: %s", payload.get("prompt", "")[:80])

        resp = requests.post(endpoint, json=payload, headers=headers, timeout=30)
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Submit failed: HTTP {resp.status_code} — {resp.text}")

        job_data = resp.json()
        task_id = job_data.get("id")
        if not task_id:
            raise RuntimeError(f"No task_id in response: {job_data}")

        logger.info("Luma task submitted: %s", task_id)

        max_wait = 600
        poll_interval = 10
        elapsed = 0

        status_url = f"https://api.lumalabs.ai/dream-machine/v1/generations/{task_id}"

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_resp = requests.get(status_url, headers=headers, timeout=15)
            if status_resp.status_code != 200:
                raise RuntimeError(f"Status check failed: HTTP {status_resp.status_code}")

            status_data = status_resp.json()
            state = status_data.get("state", "").lower()

            if state in ("completed", "finished", "succeeded"):
                video_url = status_data.get("assets", {}).get("video")
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
                "Luma generation in progress: %s%% (%ds elapsed)",
                status_data.get("progress", status_data.get("percentComplete", "?")),
                elapsed,
            )

        return error_response(
            error=f"Luma generation timed out after {max_wait}s. Task ID: {task_id}",
            error_type="timeout",
            provider=self.name,
            model=resolved_model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )


def register(ctx) -> None:
    """Register the Luma Dream Machine video generation provider."""
    ctx.register_video_gen_provider(LumaProvider())
