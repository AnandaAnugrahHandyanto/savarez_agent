"""Compatibility shim — implementation is in ``hermes_memory.memory_manager``."""

from hermes_memory.memory_manager import (
    MemoryManager,
    build_memory_context_block,
    sanitize_context,
)

__all__ = [
    "MemoryManager",
    "build_memory_context_block",
    "sanitize_context",
]
