#!/usr/bin/env python3
"""Music generation tool — thin dispatcher over provider-native backends.

Hermes doesn't bundle a music backend of its own.  Music is only
available when the active chat provider registers a native music
backend through `hermes_cli.provider_native_tools`.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from tools.registry import registry, tool_error

logger = logging.getLogger(__name__)


def music_generate_tool(
    prompt: str,
    lyrics: str,
    output_format: str = "mp3",
    sample_rate: int = 44100,
    bitrate: int = 256000,
) -> str:
    try:
        from hermes_cli.provider_native_tools import generate_music
    except Exception as exc:
        logger.debug("provider-native music dispatch unavailable: %s", exc)
        return json.dumps({
            "success": False,
            "error": "no music backend available",
        })
    result = generate_music(
        prompt=prompt,
        lyrics=lyrics,
        output_format=output_format,
        sample_rate=sample_rate,
        bitrate=bitrate,
    )
    if result is not None:
        return result
    return json.dumps({
        "success": False,
        "error": "active chat provider does not serve music_gen natively; "
                 "no other music backend is configured",
    })


def check_music_generation_requirements() -> bool:
    try:
        from hermes_cli.provider_native_tools import native_credential_present
        return native_credential_present("music_gen")
    except Exception:
        return False


MUSIC_GENERATE_SCHEMA: Dict[str, Any] = {
    "name": "music_generate",
    "description": (
        "Generate a complete sung song (with vocals) as an actual .mp3 "
        "audio file.  Takes a style prompt + lyrics and returns a local "
        "file path — NOT a prompt to paste into Suno or another service.  "
        "Use this whenever the user asks for a song, a track, or music "
        "with lyrics.  Up to ~1 minute per call.  "
        "Lyrics support structure tags: [Intro] [Verse] [Chorus] [Bridge] "
        "[Outro].  Use \\n to separate lines.  "
        "Returns JSON: `{path, format, bytes, model}`."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Style / mood description, 10–300 chars.  "
                    "Example: 'Upbeat pop, cheerful, suitable for a "
                    "travel montage'."
                ),
            },
            "lyrics": {
                "type": "string",
                "description": (
                    "Song lyrics, 10–600 chars.  Use newline to separate "
                    "lines.  Optional structure tags: [Intro] [Verse] "
                    "[Chorus] [Bridge] [Outro]."
                ),
            },
            "output_format": {
                "type": "string",
                "enum": ["mp3", "wav", "pcm"],
                "description": "Output audio container.",
                "default": "mp3",
            },
        },
        "required": ["prompt", "lyrics"],
    },
}


def _handle_music_generate(args, **_kw):
    prompt = args.get("prompt", "")
    lyrics = args.get("lyrics", "")
    if not prompt:
        return tool_error("prompt is required for music generation")
    if not lyrics:
        return tool_error("lyrics is required for music generation")
    return music_generate_tool(
        prompt=prompt,
        lyrics=lyrics,
        output_format=args.get("output_format", "mp3"),
    )


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
