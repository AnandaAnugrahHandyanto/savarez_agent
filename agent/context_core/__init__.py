"""Context engine sub-system — ToolOutputSandbox, RewindStore, GateKeeper.

Provides three composable components for fine-grained context management:

- **ToolOutputSandbox**: isolated staging area for tool outputs with pruning,
  deduplication, and summarization hooks.
- **RewindStore**: checkpoint/rollback store for conversation message state.
- **GateKeeper**: policy layer that gates when and how compression may run.

All three are designed to be used together via ContextEnginePipeline but
can also be used independently.

This package also re-exports the legacy ContextEngine from context_engine.py
to maintain backward compatibility with existing imports.
"""

from agent.context_core.sandbox import ToolOutputSandbox
from agent.context_core.rewind import RewindStore
from agent.context_core.gatekeeper import GateKeeper

# Re-export legacy ContextEngine from the file-based module for backward compat
from agent.context_engine import ContextEngine  # noqa: E402

__all__ = [
    # Legacy / file-based engine
    "ContextEngine",
    # New package components
    "ToolOutputSandbox",
    "RewindStore",
    "GateKeeper",
]
