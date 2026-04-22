#!/usr/bin/env python3
"""HappyHorse video generation tool."""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

HAPPYHORSE_BASE_URL = "https://happyhorse.app"
HAPPYHORSE_MODEL = "happyhorse-1.0/video"
DEFAULT_TIMEOUT = 60
DEFAULT_POLL_INTERVAL = 5
DEFAULT_WAIT_TIMEOUT = 300
VALID_MODES = {"std", "pro"}
VALID_ASPECT_RATIOS = {"16:9", "9:16", "1:1"}
SUCCESS_STATUSES = {"COMPLETED", "SUCCESS"}
TERMINAL_STATUSES = SUCCESS_STATUSES | {"FAILED", "CANCELLED"}


def check_happyhorse_api_key() -> bool:
    return bool(os.getenv("HAPPYHORSE_API_KEY"))


def check_happyhorse_requirements() -> bool:
    return check_happyhorse_api_key()


def _headers(api_key: Optional[str] = None) -> Dict[str, str]:
    key = api_key or os.getenv("HAPPYHORSE_API_KEY")
    if not key:
        raise ValueError("HAPPYHORSE_API_KEY is not set")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _validate_generate_args(
    *,
    prompt: Optional[str],
    mode: str,
    duration: int,
    aspect_ratio: str,
    image_urls: Optional[List[str]],
    multi_shots: bool,
    multi_prompt: Optional[List[Dict[str, Any]]],
    cfg_scale: float,
) -> None:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")
    if not isinstance(duration, int) or duration < 3 or duration > 15:
        raise ValueError("duration must be an integer between 3 and 15")
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise ValueError(f"aspect_ratio must be one of {sorted(VALID_ASPECT_RATIOS)}")
    if not isinstance(cfg_scale, (int, float)) or cfg_scale < 0 or cfg_scale > 1:
        raise ValueError("cfg_scale must be between 0 and 1")
    if multi_shots:
        if not multi_prompt:
            raise ValueError("multi_prompt is required when multi_shots=true")
    elif not prompt:
        raise ValueError("prompt is required unless multi_shots=true with multi_prompt provided")
    if image_urls is not None:
        if not isinstance(image_urls, list) or not all(isinstance(url, str) and url for url in image_urls):
            raise ValueError("image_urls must be a list of non-empty strings")


def _build_payload(
    *,
    prompt: Optional[str],
    mode: str,
    duration: int,
    aspect_ratio: str,
    image_urls: Optional[List[str]],
    sound: bool,
    cfg_scale: float,
    multi_shots: bool,
    multi_prompt: Optional[List[Dict[str, Any]]],
    happyhorse_elements: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": HAPPYHORSE_MODEL,
        "mode": mode,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "sound": sound,
        "cfg_scale": float(cfg_scale),
    }
    if prompt:
        payload["prompt"] = prompt
    if image_urls:
        payload["image_urls"] = image_urls
    if multi_shots:
        payload["multi_shots"] = True
        payload["multi_prompt"] = multi_prompt or []
    if happyhorse_elements:
        payload["happyhorse_elements"] = happyhorse_elements
    return payload


def get_happyhorse_status(task_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    response = requests.get(
        f"{HAPPYHORSE_BASE_URL}/api/status",
        headers=_headers(api_key),
        params={"task_id": task_id},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def happyhorse_video_generate(
    *,
    prompt: Optional[str] = None,
    mode: str = "std",
    duration: int = 5,
    aspect_ratio: str = "16:9",
    image_urls: Optional[List[str]] = None,
    sound: bool = True,
    cfg_scale: float = 0.5,
    multi_shots: bool = False,
    multi_prompt: Optional[List[Dict[str, Any]]] = None,
    happyhorse_elements: Optional[List[Dict[str, Any]]] = None,
    wait_for_completion: bool = False,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    timeout: int = DEFAULT_WAIT_TIMEOUT,
    api_key: Optional[str] = None,
) -> str:
    try:
        _validate_generate_args(
            prompt=prompt,
            mode=mode,
            duration=duration,
            aspect_ratio=aspect_ratio,
            image_urls=image_urls,
            multi_shots=multi_shots,
            multi_prompt=multi_prompt,
            cfg_scale=cfg_scale,
        )
        payload = _build_payload(
            prompt=prompt,
            mode=mode,
            duration=duration,
            aspect_ratio=aspect_ratio,
            image_urls=image_urls,
            sound=sound,
            cfg_scale=cfg_scale,
            multi_shots=multi_shots,
            multi_prompt=multi_prompt,
            happyhorse_elements=happyhorse_elements,
        )
        response = requests.post(
            f"{HAPPYHORSE_BASE_URL}/api/generate",
            headers=_headers(api_key),
            json=payload,
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
        data = response_data.get("data", {})
        result: Dict[str, Any] = {
            "success": True,
            "task_id": data.get("task_id"),
            "status": data.get("status"),
            "response": response_data,
        }

        if not wait_for_completion:
            return json.dumps(result, ensure_ascii=False)

        task_id = data.get("task_id")
        if not task_id:
            raise ValueError("HappyHorse response did not include task_id")
        deadline = time.time() + timeout
        while time.time() <= deadline:
            status_response = get_happyhorse_status(task_id, api_key=api_key)
            status_data = status_response.get("data", {})
            status = status_data.get("status")
            result.update({
                "status": status,
                "status_response": status_response,
            })
            if status in SUCCESS_STATUSES:
                urls = ((status_data.get("response") or {}).get("resultUrls") or [])
                result["video_url"] = urls[0] if urls else None
                return json.dumps(result, ensure_ascii=False)
            if status in TERMINAL_STATUSES:
                return json.dumps(result, ensure_ascii=False)
            time.sleep(max(0, poll_interval))
        result["success"] = False
        result["error"] = f"Timed out waiting for HappyHorse task {task_id}"
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.exception("HappyHorse video generation failed: %s", exc)
        return json.dumps(
            {
                "success": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            ensure_ascii=False,
        )


VIDEO_GENERATE_SCHEMA = {
    "name": "video_generate",
    "description": "Generate videos with HappyHorse AI. Supports text-to-video, image-to-video, and optional polling until the final video URL is ready.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Video prompt. Required unless multi_shots=true with multi_prompt provided.",
            },
            "mode": {
                "type": "string",
                "enum": ["std", "pro"],
                "default": "std",
            },
            "duration": {
                "type": "integer",
                "minimum": 3,
                "maximum": 15,
                "default": 5,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1"],
                "default": "16:9",
            },
            "image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional image URLs for image-to-video generation.",
            },
            "sound": {
                "type": "boolean",
                "default": True,
            },
            "cfg_scale": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.5,
            },
            "multi_shots": {
                "type": "boolean",
                "default": False,
            },
            "multi_prompt": {
                "type": "array",
                "description": "Optional multi-shot prompt array.",
            },
            "happyhorse_elements": {
                "type": "array",
                "description": "Optional HappyHorse character/element definitions.",
            },
            "wait_for_completion": {
                "type": "boolean",
                "default": False,
                "description": "When true, poll /api/status until the task completes or times out.",
            },
            "poll_interval": {
                "type": "integer",
                "minimum": 0,
                "default": 5,
            },
            "timeout": {
                "type": "integer",
                "minimum": 1,
                "default": 300,
            },
        },
        "required": [],
    },
}


def _handle_video_generate(args, **_kw):
    if not args.get("multi_shots") and not args.get("prompt"):
        return tool_error("prompt is required unless multi_shots=true with multi_prompt provided")
    return happyhorse_video_generate(
        prompt=args.get("prompt"),
        mode=args.get("mode", "std"),
        duration=args.get("duration", 5),
        aspect_ratio=args.get("aspect_ratio", "16:9"),
        image_urls=args.get("image_urls"),
        sound=args.get("sound", True),
        cfg_scale=args.get("cfg_scale", 0.5),
        multi_shots=args.get("multi_shots", False),
        multi_prompt=args.get("multi_prompt"),
        happyhorse_elements=args.get("happyhorse_elements"),
        wait_for_completion=args.get("wait_for_completion", False),
        poll_interval=args.get("poll_interval", DEFAULT_POLL_INTERVAL),
        timeout=args.get("timeout", DEFAULT_WAIT_TIMEOUT),
    )


registry.register(
    name="video_generate",
    toolset="image_gen",
    schema=VIDEO_GENERATE_SCHEMA,
    handler=_handle_video_generate,
    check_fn=check_happyhorse_requirements,
    requires_env=["HAPPYHORSE_API_KEY"],
    is_async=False,
    emoji="🎬",
)
