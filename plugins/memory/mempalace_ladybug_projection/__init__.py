from __future__ import annotations

from .provider import MemPalaceLadybugProjectionProvider


def register(ctx):
    ctx.register_memory_provider(MemPalaceLadybugProjectionProvider())


__all__ = ["MemPalaceLadybugProjectionProvider"]
