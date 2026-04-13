#!/usr/bin/env python3
"""Music generation tool backed by FAL's Minimax music endpoint."""

import datetime
import json
import logging

from tools import image_generation_tool
from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "fal-ai/minimax-music/v2.6"
MIN_PROMPT_LENGTH = 10
MAX_PROMPT_LENGTH = 300
MAX_LYRICS_LENGTH = 1000


def _validate_prompt(prompt: str) -> str:
    if not isinstance(prompt, str):
        raise ValueError("prompt must be a string")

    normalized_prompt = prompt.strip()
    if not normalized_prompt:
        raise ValueError("prompt is required and must be a non-empty string")

    if len(normalized_prompt) < MIN_PROMPT_LENGTH or len(normalized_prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(
            f"prompt must be between {MIN_PROMPT_LENGTH} and {MAX_PROMPT_LENGTH} characters"
        )

    return normalized_prompt


def _validate_lyrics(lyrics, instrumental: bool) -> str:
    if lyrics is None:
        normalized_lyrics = ""
    elif not isinstance(lyrics, str):
        raise ValueError("lyrics must be a string")
    else:
        normalized_lyrics = lyrics.strip()

    if not instrumental and not normalized_lyrics:
        raise ValueError("lyrics are required when instrumental is false")

    if len(normalized_lyrics) > MAX_LYRICS_LENGTH:
        raise ValueError(f"lyrics must be {MAX_LYRICS_LENGTH} characters or fewer")

    return normalized_lyrics


def music_generate_tool(
    prompt: str,
    instrumental: bool = True,
    lyrics: str = "",
) -> str:
    """Generate a music clip from a text prompt via FAL."""
    start_time = datetime.datetime.now()

    try:
        if not image_generation_tool.check_image_generation_requirements():
            raise ValueError("FAL music generation is unavailable because FAL credentials are not configured")

        validated_prompt = _validate_prompt(prompt)
        validated_lyrics = _validate_lyrics(lyrics, instrumental)
        arguments = {
            "prompt": validated_prompt,
            "is_instrumental": instrumental,
        }
        if validated_lyrics:
            arguments["lyrics"] = validated_lyrics

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
                "instrumental": instrumental,
                "lyrics_provided": bool(validated_lyrics),
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
    "description": "Generate music from a text prompt using FAL's Minimax Music model. Supports either instrumental tracks or lyric-based songs and returns a downloadable audio URL.",
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Describe the style, mood, genre, instrumentation, and scenario for the music you want.",
                "minLength": MIN_PROMPT_LENGTH,
                "maxLength": MAX_PROMPT_LENGTH,
            },
            "instrumental": {
                "type": "boolean",
                "description": "When true, generate instrumental music without vocals. When false, provide lyrics for the sung track.",
                "default": True,
            },
            "lyrics": {
                "type": "string",
                "description": "Lyrics for the song. Required when instrumental is false.",
                "maxLength": MAX_LYRICS_LENGTH,
                "default": "",
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
        instrumental=args.get("instrumental", True),
        lyrics=args.get("lyrics", ""),
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
