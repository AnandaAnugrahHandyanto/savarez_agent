"""Computer use toolset — universal desktop control for tool-capable models.

Architecture
------------
This toolset drives desktop applications through a platform backend while
keeping one model-facing OpenAI function-calling schema:

* macOS uses cua-driver's background computer-use primitive (SkyLight private
  SPIs for focus-without-raise + pid-scoped event posting). It does NOT steal
  the user's cursor, keyboard focus, or Space, so the agent and user can
  co-work on the same machine.
* Linux uses the companion linux-computer-use MCP driver. The current Linux path
  is X11-first and mirrors the cua-driver tool surface, but Linux window
  managers may move the real pointer/focus because they do not expose macOS's
  private background event primitive.

Unlike #4562's Anthropic-native `computer_20251124` tool, the schema here is a
plain OpenAI function-calling schema that every tool-capable model can drive.
Vision models get SOM (set-of-mark) captures — a screenshot with numbered
overlays on every interactable element plus the AX/AT-SPI tree — so they click
by element index instead of pixel coordinates. Non-vision models can drive via
the accessibility tree alone.

Wiring
------
* `tool.py`          — registers the `computer_use` tool via tools.registry.
* `backend.py`       — abstract `ComputerUseBackend`; swappable implementation.
* `cua_backend.py`   — macOS backend; speaks MCP over stdio to `cua-driver`.
* `linux_backend.py` — Linux backend; speaks MCP over stdio to
                       `linux-computer-use mcp`.
* `schema.py`        — shared model-agnostic schema + docstring.

The outer integration points (multimodal tool-result plumbing, screenshot
eviction in the Anthropic adapter, image-aware token estimation, the
COMPUTER_USE_GUIDANCE prompt block, approval hook, and skills/docs) live
alongside this package. See agent/anthropic_adapter.py and
agent/prompt_builder.py for the salvaged hunks from PR #4562.
"""

from __future__ import annotations

# Re-export the public surface so `from tools.computer_use import ...` works.
from tools.computer_use.tool import (  # noqa: F401
    handle_computer_use,
    set_approval_callback,
    check_computer_use_requirements,
    get_computer_use_schema,
)
