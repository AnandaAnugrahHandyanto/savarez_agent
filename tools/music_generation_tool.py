#!/usr/bin/env python3
"""Music generation tool backed by FAL's ElevenLabs music endpoint."""

import datetime
import json
import logging

from tools import image_generation_tool
from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "fal-ai/elevenlabs/music"
DEFAULT_DURATION_SECONDS = 30
MIN_DURATION_SECONDS = 10
MAX_DURATION_SECONDS = 300


def _validate_duration_seconds(duration_seconds) -> int:
    if duration_seconds is None:
        return DEFAULT_DURATION_SECONDS
    if not isinstance(duration_seconds, int):
        raise ValueError("duration_seconds must be an integer")
    if duration_seconds < MIN_DURATION_SECONDS or duration_seconds > MAX_DURATION_SECONDS:
        raise ValueError(
            f"duration_seconds must be between {MIN_DURATION_SECONDS} and {MAX_DURATION_SECONDS}"
        )
    return duration_seconds


def music_generate_tool(
    prompt: str,
    duration_seconds: int = DEFAULT_DURATION_SECONDS,
    instrumental: bool = True,
) -> str:
    """Generate a music clip from a text prompt via FAL."""
    start_time = datetime.datetime.now()

    try:
        if not prompt or not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt is required and must be a non-empty string")

        if not image_generation_tool.check_image_generation_requirements():
            raise ValueError("FAL music generation is unavailable because FAL credentials are not configured")

        validated_duration = _validate_duration_seconds(duration_seconds)
        arguments = {
            "prompt": prompt.strip(),
            "music_length_ms": validated_duration * 1000,
        }
        if instrumental:
            arguments["force_instrumental"] = True

        logger.info("Submitting music generation request to %s", DEFAULT_MODEL)
        handler = image_generation_tool._submit_fal_request(DEFAULT_MODEL, arguments=arguments)
        result = handler.get()

        audio = result.get("audio") if isinstance(result, dict) else None
        audio_url = audio.get("url") if isinstance(audio, dict) else None
        if not audio_url:
            raise ValueError("Invalid response from FAL.ai API - no audio URL returned")

        return json.dumps(
            {
                "success": True,
                "audio": audio_url,
                "content_type": audio.get("content_type"),
                "file_name": audio.get("file_name"),
                "duration_seconds": validated_duration,
            },
            indent=2,
            ensure_ascii=False,
        )
    except Exception as e:
        logger.error("Error generating music: %s", e, exc_info=True)
        return json.dumps(
            {
                "success": False,
                "audio": None,
                "error": str(e),
                "error_type": type(e).__name__,
                "generation_time": (
                    datetime.datetime.now() - start_time
                ).total_seconds(),
            },
            indent=2,
            ensure_ascii=False,
        )


MUSIC_GENERATE_SCHEMA = {
    "name": "music_generate",
    "description": "Generate a short music clip from a text prompt using FAL. Returns a downloadable audio URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Describe the mood, style, instrumentation, and pacing you want in the generated music.",
            },
            "duration_seconds": {
                "type": "integer",
                "description": "Target clip length in seconds.",
                "default": DEFAULT_DURATION_SECONDS,
                "minimum": MIN_DURATION_SECONDS,
                "maximum": MAX_DURATION_SECONDS,
            },
            "instrumental": {
                "type": "boolean",
                "description": "When true, force instrumental music without vocals.",
                "default": True,
            },
        },
        "required": ["prompt"],
    },
}


def _handle_music_generate(args, **kw):
    prompt = args.get("prompt", "")
    if not prompt:
        return tool_error("prompt is required for music generation")
    return music_generate_tool(
        prompt=prompt,
        duration_seconds=args.get("duration_seconds", DEFAULT_DURATION_SECONDS),
        instrumental=args.get("instrumental", True),
    )


def check_music_generation_requirements() -> bool:
    return image_generation_tool.check_image_generation_requirements()


registry.register(
    name="music_generate",
    toolset="music_gen",
    schema=MUSIC_GENERATE_SCHEMA,
    handler=_handle_music_generate,
    check_fn=check_music_generation_requirements,
    requires_env=[],
    is_async=False,
    emoji="🎵",
)
