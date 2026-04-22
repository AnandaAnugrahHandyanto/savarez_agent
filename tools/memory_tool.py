#!/usr/bin/env python3
"""
Memory tool entry — registers with ``tools.registry``.

Implementation lives in ``hermes_memory.builtin_memory_tool`` so the memory
subsystem is grouped under the ``hermes_memory/`` package.
"""

from hermes_memory.builtin_memory_tool import (
    ENTRY_DELIMITER,
    MEMORY_SCHEMA,
    MemoryStore,
    check_memory_requirements,
    get_memory_dir,
    memory_tool,
    msvcrt,
)
from hermes_memory.builtin_memory_tool import fcntl as fcntl

from tools.registry import registry

__all__ = [
    "ENTRY_DELIMITER",
    "MEMORY_SCHEMA",
    "MemoryStore",
    "check_memory_requirements",
    "fcntl",
    "get_memory_dir",
    "memory_tool",
    "msvcrt",
]

registry.register(
    name="memory",
    toolset="memory",
    schema=MEMORY_SCHEMA,
    handler=lambda args, **kw: memory_tool(
        action=args.get("action", ""),
        target=args.get("target", "memory"),
        content=args.get("content"),
        old_text=args.get("old_text"),
        store=kw.get("store")),
    check_fn=check_memory_requirements,
    emoji="🧠",
)
