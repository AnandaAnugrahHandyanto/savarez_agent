"""WaveSpeed image generation backend.

Exposes a curated set of WaveSpeed-hosted text-to-image models as an
``ImageGenProvider`` implementation.

The provider uses WaveSpeed's REST API with ``enable_sync_mode=true`` so most
requests return a finished result in one round trip. If the API still returns a
pending task, Hermes polls the prediction result endpoint briefly before
surfacing a timeout.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO,
    ImageGenProvider,
    error_response,
    resolve_aspect_ratio,
    success_response,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.wavespeed.ai/api/v3"
DEFAULT_TIMEOUT = 120
POLL_INTERVAL_SECONDS = 2.0
POLL_TIMEOUT_SECONDS = 90.0

_MODELS: Dict[str, Dict[str, Any]] = {
    "wavespeed-ai/flux-2-klein-9b/text-to-image": {
        "display": "WaveSpeed FLUX 2 Klein 9B",
        "speed": "<2s",
        "strengths": "Fast general-purpose image generation",
        "price": "see WaveSpeed",
        "aspect_style": "size",
        "sizes": {
            "landscape": "1360*768",
            "square": "1024*1024",
            "portrait": "768*1360",
        },
        "defaults": {},
    },
    "wavespeed-ai/flux-2-pro/text-to-image": {
        "display": "WaveSpeed FLUX 2 Pro",
        "speed": "~6s",
        "strengths": "Higher-fidelity photorealism",
        "price": "see WaveSpeed",
        "aspect_style": "size",
        "sizes": {
            "landscape": "1360*768",
            "square": "1024*1024",
            "portrait": "768*1360",
        },
        "defaults": {},
    },
    "google/nano-banana-pro/text-to-image": {
        "display": "Google Nano Banana Pro",
        "speed": "~8s",
        "strengths": "Prompt adherence, text rendering, 4K-capable family",
        "price": "see WaveSpeed",
        "aspect_style": "aspect_ratio",
        "sizes": {
            "landscape": "16:9",
            "square": "1:1",
            "portrait": "9:16",
        },
        "defaults": {
            "resolution": "1k",
            "output_format": "png",
        },
    },
}

DEFAULT_MODEL = "wavespeed-ai/flux-2-klein-9b/text-to-image"


def _base_url() -> str:
    return (os.getenv("WAVESPEED_API_BASE_URL") or DEFAULT_BASE_URL).strip().rstrip("/")


def _headers() -> Dict[str, str]:
    api_key = (os.getenv("WAVESPEED_API_KEY") or "").strip()
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _load_wavespeed_config() -> Dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        cfg = load_config()
        section = cfg.get("image_gen") if isinstance(cfg, dict) else None
        if not isinstance(section, dict):
            return {}
        wavespeed_section = section.get("wavespeed")
        if isinstance(wavespeed_section, dict):
            merged = dict(section)
            merged.update({"wavespeed": dict(wavespeed_section)})
            return merged
        return section
    except Exception as exc:
        logger.debug("Could not load image_gen config for WaveSpeed: %s", exc)
        return {}


def _resolve_model() -> Tuple[str, Dict[str, Any]]:
    env_override = (os.getenv("WAVESPEED_IMAGE_MODEL") or "").strip()
    if env_override in _MODELS:
        return env_override, _MODELS[env_override]

    cfg = _load_wavespeed_config()
    nested = cfg.get("wavespeed") if isinstance(cfg.get("wavespeed"), dict) else {}
    candidate = nested.get("model") if isinstance(nested.get("model"), str) else None
    if not candidate:
        top = cfg.get("model")
        if isinstance(top, str):
            candidate = top

    if candidate in _MODELS:
        return candidate, _MODELS[candidate]

    return DEFAULT_MODEL, _MODELS[DEFAULT_MODEL]


def _build_payload(model_id: str, prompt: str, aspect_ratio: str) -> Dict[str, Any]:
    meta = _MODELS[model_id]
    aspect = resolve_aspect_ratio(aspect_ratio)
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "enable_sync_mode": True,
        "enable_base64_output": False,
    }
    payload.update(meta.get("defaults", {}))

    style = meta["aspect_style"]
    if style == "size":
        payload["size"] = meta["sizes"][aspect]
    elif style == "aspect_ratio":
        payload["aspect_ratio"] = meta["sizes"][aspect]
    else:
        raise ValueError(f"Unknown WaveSpeed aspect style: {style}")

    return payload


def _prediction_result_url(task_data: Dict[str, Any]) -> Optional[str]:
    direct_candidates = (
        task_data.get("result_url"),
        task_data.get("result"),
        task_data.get("response_url"),
    )
    for candidate in direct_candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    urls = task_data.get("urls")
    if isinstance(urls, dict):
        for key in ("get", "result", "status", "self"):
            url = urls.get(key)
            if isinstance(url, str) and url.strip():
                return url.strip()
    task_id = task_data.get("id")
    if isinstance(task_id, str) and task_id.strip():
        return f"{_base_url()}/predictions/{task_id.strip()}/result"
    return None


def _extract_image_result(task_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    def _extract_from_item(item: Any) -> Optional[str]:
        if isinstance(item, str) and item.strip():
            return item.strip()
        if not isinstance(item, dict):
            return None

        for key in ("url", "output", "result", "image_url"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        image_value = item.get("image")
        if isinstance(image_value, str) and image_value.strip():
            return image_value.strip()
        if isinstance(image_value, dict):
            nested_url = image_value.get("url") or image_value.get("output")
            if isinstance(nested_url, str) and nested_url.strip():
                return nested_url.strip()

        return None

    outputs = task_data.get("outputs")
    if isinstance(outputs, list):
        for item in outputs:
            image_ref = _extract_from_item(item)
            if image_ref:
                return image_ref, None
    if isinstance(outputs, str) and outputs.strip():
        return outputs.strip(), None

    for key in ("output", "result", "image_url"):
        value = task_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), None

    image_value = task_data.get("image")
    if isinstance(image_value, str) and image_value.strip():
        return image_value.strip(), None
    if isinstance(image_value, dict):
        nested_url = image_value.get("url") or image_value.get("output")
        if isinstance(nested_url, str) and nested_url.strip():
            return nested_url.strip(), None

    error = task_data.get("error")
    if isinstance(error, str) and error.strip():
        return None, error.strip()
    return None, None


def _poll_until_complete(result_url: str) -> Dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    last_status = ""
    while time.monotonic() < deadline:
        response = requests.get(result_url, headers=_headers(), timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            raise ValueError("WaveSpeed returned an invalid polling response")

        status = str(data.get("status") or "").strip().lower()
        last_status = status or last_status
        if status == "completed":
            return data
        if status == "failed":
            error = data.get("error") or "WaveSpeed task failed"
            raise ValueError(str(error))
        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(
        f"WaveSpeed image generation did not complete within {int(POLL_TIMEOUT_SECONDS)}s"
        + (f" (last status: {last_status})" if last_status else "")
    )


class WaveSpeedImageGenProvider(ImageGenProvider):
    @property
    def name(self) -> str:
        return "wavespeed"

    @property
    def display_name(self) -> str:
        return "WaveSpeed"

    def is_available(self) -> bool:
        return bool((os.getenv("WAVESPEED_API_KEY") or "").strip())

    def list_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": model_id,
                "display": meta["display"],
                "speed": meta["speed"],
                "strengths": meta["strengths"],
                "price": meta["price"],
            }
            for model_id, meta in _MODELS.items()
        ]

    def default_model(self) -> Optional[str]:
        return DEFAULT_MODEL

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "WaveSpeed",
            "badge": "paid",
            "tag": "Native WaveSpeed image generation via REST API",
            "env_vars": [
                {
                    "key": "WAVESPEED_API_KEY",
                    "prompt": "WaveSpeed API key",
                    "url": "https://wavespeed.ai/accesskey",
                },
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
                provider="wavespeed",
                aspect_ratio=aspect,
            )

        if not self.is_available():
            return error_response(
                error=(
                    "WAVESPEED_API_KEY not set. Run `hermes tools` -> Image "
                    "Generation -> WaveSpeed to configure it."
                ),
                error_type="auth_required",
                provider="wavespeed",
                aspect_ratio=aspect,
            )

        model_id, _meta = _resolve_model()
        payload = _build_payload(model_id, prompt, aspect)
        request_url = f"{_base_url()}/{model_id}"

        try:
            response = requests.post(
                request_url,
                headers=_headers(),
                json=payload,
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response else 0
            detail = ""
            if exc.response is not None:
                try:
                    err_body = exc.response.json()
                    detail = err_body.get("message") or err_body.get("error") or ""
                except Exception:
                    detail = exc.response.text[:300]
            message = f"WaveSpeed image generation failed ({status})"
            if detail:
                message += f": {detail}"
            return error_response(
                error=message,
                error_type="api_error",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.Timeout:
            return error_response(
                error=f"WaveSpeed image generation timed out ({DEFAULT_TIMEOUT}s)",
                error_type="timeout",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.ConnectionError as exc:
            return error_response(
                error=f"WaveSpeed connection error: {exc}",
                error_type="connection_error",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"WaveSpeed returned an invalid response: {exc}",
                error_type="invalid_response",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict):
            return error_response(
                error="WaveSpeed returned no prediction payload",
                error_type="invalid_response",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        status = str(data.get("status") or "").strip().lower()
        image_ref, task_error = _extract_image_result(data)
        if image_ref:
            return success_response(
                image=image_ref,
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
                provider="wavespeed",
            )

        if status == "failed":
            return error_response(
                error=task_error or "WaveSpeed task failed",
                error_type="api_error",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        result_url = _prediction_result_url(data)
        if not result_url:
            return error_response(
                error="WaveSpeed returned no result URL and no outputs",
                error_type="invalid_response",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )

        try:
            final_data = _poll_until_complete(result_url)
            image_ref, task_error = _extract_image_result(final_data)
            if image_ref:
                return success_response(
                    image=image_ref,
                    model=model_id,
                    prompt=prompt,
                    aspect_ratio=aspect,
                    provider="wavespeed",
                )
            return error_response(
                error=task_error or "WaveSpeed completed without returning an image",
                error_type="empty_response",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except TimeoutError as exc:
            return error_response(
                error=str(exc),
                error_type="timeout",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response else 0
            return error_response(
                error=f"WaveSpeed polling failed ({status_code})",
                error_type="api_error",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except requests.RequestException as exc:
            return error_response(
                error=f"WaveSpeed polling error: {exc}",
                error_type="connection_error",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )
        except Exception as exc:
            return error_response(
                error=f"WaveSpeed polling returned an invalid response: {exc}",
                error_type="invalid_response",
                provider="wavespeed",
                model=model_id,
                prompt=prompt,
                aspect_ratio=aspect,
            )


def register(ctx: Any) -> None:
    ctx.register_image_gen_provider(WaveSpeedImageGenProvider())
