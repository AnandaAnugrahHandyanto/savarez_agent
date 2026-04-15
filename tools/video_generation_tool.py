#!/usr/bin/env python3
"""Video generation tool — thin dispatcher over provider-native backends.

Hermes doesn't bundle a video backend of its own.  Video is only
available when the active chat provider registers a native video
backend through `hermes_cli.provider_native_tools`.  When no such
backend is configured, the tool is simply not available
(`check_video_generation_requirements` returns `False`).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


def video_generate_tool(
    prompt: str,
    duration: Optional[int] = None,
    resolution: Optional[str] = None,
    first_frame_image: Optional[str] = None,
) -> str:
    try:
        from hermes_cli.provider_native_tools import generate_video
    except Exception as exc:
        logger.debug("provider-native video dispatch unavailable: %s", exc)
        return json.dumps({
            "success": False,
            "error": "no video backend available",
        })
    result = generate_video(
        prompt=prompt,
        duration=duration,
        resolution=resolution,
        first_frame_image=first_frame_image,
    )
    if result is not None:
        return result
    return json.dumps({
        "success": False,
        "error": "active chat provider does not serve video_gen natively; "
                 "no other video backend is configured",
    })


def check_video_generation_requirements() -> bool:
    """Tool is available iff the active provider has a native video backend
    with a configured credential."""
    try:
        from hermes_cli.provider_native_tools import native_credential_present
        return native_credential_present("video_gen")
    except Exception:
        return False


VIDEO_GENERATE_SCHEMA: Dict[str, Any] = {
    "name": "video_generate",
    "description": (
        "Generate a short video clip (6 or 10 seconds) as an actual .mp4 "
        "file from a text prompt.  Returns a local file path — NOT a "
        "suggestion to use Runway/Pika/Sora/etc.  Use this whenever the "
        "user asks for a video or a short clip.  Generation is slow "
        "(typically 1–5 minutes); proceed without asking for confirmation "
        "unless the prompt is ambiguous.  "
        "Returns JSON: `{path, url, model, task_id}`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Detailed description of the scene to render.",
            },
            "duration": {
                "type": "integer",
                "enum": [6, 10],
                "description": "Video length in seconds.",
                "default": 6,
            },
            "resolution": {
                "type": "string",
                "enum": ["768P", "1080P"],
                "description": "Output resolution.",
                "default": "768P",
            },
            "first_frame_image": {
                "type": "string",
                "description": "Optional first-frame image (local path, "
                               "http(s) URL, or data: URI).  When set, an "
                               "image-to-video model is used.",
            },
        },
        "required": ["prompt"],
    },
}


def _handle_video_generate(args, **_kw):
    prompt = args.get("prompt", "")
    if not prompt:
        return tool_error("prompt is required for video generation")
    return video_generate_tool(
        prompt=prompt,
        duration=args.get("duration"),
        resolution=args.get("resolution"),
        first_frame_image=args.get("first_frame_image"),
    )


registry.register(
    name="video_generate",
    toolset="video_gen",
    schema=VIDEO_GENERATE_SCHEMA,
    handler=_handle_video_generate,
    check_fn=check_video_generation_requirements,
    requires_env=[],
    is_async=False,
    emoji="🎬",
)
