"""Mem0 Platform integration for persistent memory.

This package is only active when enabled in mem0.json config
and MEM0_API_KEY is set. All mem0ai imports are deferred
to avoid ImportError when the package is not installed.

Named ``mem0_integration`` (not ``mem0``) to avoid shadowing the
``mem0`` package installed by the ``mem0ai`` SDK.
"""
