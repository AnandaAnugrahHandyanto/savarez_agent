"""Phonetic Captions plugin — registration.

Wires the video-caption pipeline tool into the Hermes plugin system.
The dashboard (FastAPI routes + React UI) is discovered separately via
dashboard/manifest.json — no registration needed here for that surface.
"""

from . import pipeline


def register(ctx) -> None:
    """Called once at startup by the Hermes plugin loader."""
    ctx.register_tool(
        name="video-caption",
        toolset="phonetic-captions",
        schema=pipeline.SCHEMA,
        handler=lambda args, **kw: pipeline._handle_caption(args, **kw),
        check_fn=pipeline.check_requirements,
        emoji="🎬",
    )
