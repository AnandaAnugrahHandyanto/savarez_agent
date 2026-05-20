"""Thin Hermes adapter skeleton for ContextOps/ESE.

This package is the *only* Hermes-resident ContextOps code. It holds no
ContextOps core logic — routing, heat, context-pack construction all live in
the standalone ``contextops_ese`` package. The adapter merely:

* reads a fail-safe config block (``context.contextops``),
* optionally imports the ``contextops_ese`` core,
* builds a read-only context pack *preview*,
* and fails closed (returns ``None``) on any missing/disabled/invalid/unsafe
  condition.

It deliberately does NOT touch ``gateway/run.py`` or
``agent/prompt_builder.py`` and performs no dispatch, no memory writes, and
no prompt injection.
"""

from .adapter import ContextOpsAdapter, default_config

__all__ = ["ContextOpsAdapter", "default_config"]
