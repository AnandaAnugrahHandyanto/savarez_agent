"""RunwayML video generation backend.

User-facing surface: pick a **model** (``gen3a-turbo`` or ``gen3a-standard``).
The plugin auto-routes to Runway's ``/v1/generations`` endpoint. The agent never
sees the routing — it just calls ``video_generate(prompt=..., image_url=...)``.

Model tiers:
  turbo       gen3a_turbo    — Fast, ~2-3 min generation, lower cost
  standard    gen3a_standard — High quality, ~5 min generation, higher cost

Selection precedence for the active model:
    1. ``model=`` arg from the tool call
    2. ``RUNWAY_VIDEO_MODEL`` env var
    3. ``video_gen.runway.model`` in ``config.yaml``
    4. ``video_gen.model`` in ``config.yaml`` (when it's one of our model IDs)
    5. ``DEFAULT_MODEL`` (gen3a-turbo)

Authentication via ``RUNWAY_API_KEY`` (Bearer token). Output is an HTTPS URL
from Runway's CDN; the gateway downloads and delivers it.
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

RUNWAY_MODELS: Dict[str, Dict[str, Any]] = {
    "gen3a-turbo": {
        "display": "Gen-3 Alpha Turbo",
        "model_id": "gen3a_turbo",
        "speed": "~2-3 min",
        "price": "$0.10/s",
        "strengths": "Fast generation, good for iteration",
        "modalities": ["text", "image"],
    },
    "gen3a-standard": {
        "display": "Gen-3 Alpha Standard",
        "model_id": "gen3a_standard",
        "speed": "~5 min",
        "price": "$0.20/s",
        "strengths": "Highest cinematic quality, better prompt adherence",
        "modalities": ["text", "image"],
    },
}

DEFAULT_MODEL = "gen3a-turbo"

# Runway's supported parameters
SUPPORTED_ASPECT_RATIOS = ("16:9", "9:16", "1:1")
SUPPORTED_DURATIONS = (5, 10)  # 5s or 10s only


class RunwayProvider(VideoGenProvider):
    """RunwayML Gen-3 Alpha backend."""

    @property
    def name(self) -> str:
        return "runway"

    @property
    def display_name(self) -> str:
        return "RunwayML"

    def is_available(self) -> bool:
        return bool(os.environ.get("RUNWAY_API_KEY"))

    def list_models(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for mid, meta in RUNWAY_MODELS.items():
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
            "resolutions": list(COMMON_RESOLUTIONS),  # Runway auto-handles
            "min_duration": 5,
            "max_duration": 10,
            "supports_audio": False,
            "supports_negative_prompt": False,
            "max_reference_images": 0,
        }

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "RunwayML",
            "badge": "paid",
            "tag": "Cinematic video generation with Gen-3 Alpha",
            "env_vars": [
                {
                    "key": "RUNWAY_API_KEY",
                    "prompt": "RunwayML API key",
                    "url": "https://runwayml.com/api-keys",
                },
            ],
        }

    # -----------------------------------------------------------------------
    # Model resolution
    # -----------------------------------------------------------------------

    def _resolve_model(self, model: Optional[str]) -> str:
        """Pick the active model ID.

        Precedence: arg > env > config > default.
        """
        if model and model in RUNWAY_MODELS:
            return model

        env_model = os.environ.get("RUNWAY_VIDEO_MODEL")
        if env_model and env_model in RUNWAY_MODELS:
            return env_model

        try:
            from hermes_cli.config import load_config

            cfg = load_config()
            runway_section = (cfg or {}).get("video_gen", {})
            if isinstance(runway_section, dict):
                config_model = runway_section.get("runway", {}).get("model")
                if isinstance(config_model, str) and config_model in RUNWAY_MODELS:
                    return config_model

                # Fallback to generic video_gen.model
                generic_model = runway_section.get("model")
                if isinstance(generic_model, str) and generic_model in RUNWAY_MODELS:
                    return generic_model
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
        """Generate video via RunwayML API.

        Routing: image_url presence picks image-to-video vs text-to-video.
        Runway uses the same endpoint for both — the presence of ``image_prompt``
        in the payload triggers image-to-video mode internally.
        """
        resolved_model = self._resolve_model(model)
        model_meta = RUNWAY_MODELS[resolved_model]
        model_id = model_meta["model_id"]

        # Clamp aspect ratio
        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            aspect_ratio = DEFAULT_ASPECT_RATIO

        # Clamp duration: Runway only supports 5 or 10
        if duration is None:
            duration = 5
        elif duration <= 5:
            duration = 5
        else:
            duration = 10

        api_key = os.environ.get("RUNWAY_API_KEY")
        if not api_key:
            return error_response(
                error="RUNWAY_API_KEY not set. Set it via `hermes tools` → Video Generation.",
                error_type="missing_api_key",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )

        # Build payload
        payload: Dict[str, Any] = {
            "model": model_id,
            "promptText": prompt,
            "duration_seconds": duration,
            "ratio": aspect_ratio,
        }

        # Image-to-video: Runway expects base64 or URL in image_prompt
        modality_used = "text"
        if image_url:
            payload["image_prompt"] = image_url
            modality_used = "image"

        # Optional seed
        if seed is not None:
            payload["seed"] = seed

        # Make the request
        try:
            return self._submit_and_poll(
                payload=payload,
                api_key=api_key,
                resolved_model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration=duration,
                modality=modality_used,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Runway API request failed: %s", exc)
            return error_response(
                error=f"Runway API error: {exc}",
                error_type="api_error",
                provider=self.name,
                model=resolved_model,
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )
        except Exception as exc:
            logger.error("Runway generation failed: %s", exc)
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
        api_key: str,
        resolved_model: str,
        prompt: str,
        aspect_ratio: str,
        duration: int,
        modality: str,
    ) -> Dict[str, Any]:
        """Submit generation job and poll until complete."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # 1. Submit the generation job
        submit_url = "https://api.runwayml.com/v1/generations"
        logger.info("Submitting Runway generation: %s", payload.get("promptText", "")[:80])

        resp = requests.post(submit_url, json=payload, headers=headers, timeout=30)
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"Submit failed: HTTP {resp.status_code} — {resp.text}")

        job_data = resp.json()
        task_id = job_data.get("id")
        if not task_id:
            raise RuntimeError(f"No task_id in response: {job_data}")

        logger.info("Runway task submitted: %s", task_id)

        # 2. Poll until complete
        max_wait = 600  # 10 minutes
        poll_interval = 10
        elapsed = 0

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_url = f"https://api.runwayml.com/v1/generations/{task_id}"
            status_resp = requests.get(status_url, headers=headers, timeout=15)
            if status_resp.status_code != 200:
                raise RuntimeError(f"Status check failed: HTTP {status_resp.status_code}")

            status_data = status_resp.json()
            state = status_data.get("state", "").lower()

            logger.debug("Runway task %s: %s (%d%%)", task_id, state, status_data.get("percentComplete", 0))

            if state in ("succeeded", "completed", "done"):
                # Extract video URL
                video_url = status_data.get("output", {}).get("video", {}).get("url")
                if not video_url:
                    # Try alternative response shapes
                    video_url = status_data.get("output", {}).get("url") or status_data.get("url")

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
                else:
                    raise RuntimeError(f"No video URL in completed job: {status_data}")

            elif state in ("failed", "error"):
                error_msg = status_data.get("error", {}).get("message", "Unknown error")
                raise RuntimeError(f"Generation failed: {error_msg}")

            # Still processing, continue polling
            logger.info(
                "Runway generation in progress: %s%% (%ds elapsed)",
                status_data.get("percentComplete", "?"),
                elapsed,
            )

        # Timeout
        return error_response(
            error=f"Runway generation timed out after {max_wait}s. Task ID: {task_id}. Check status at https://runwayml.com/my-projects",
            error_type="timeout",
            provider=self.name,
            model=resolved_model,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
        )


def register(ctx) -> None:
    """Register the RunwayML video generation provider."""
    ctx.register_video_gen_provider(RunwayProvider())
