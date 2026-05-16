"""SomaEngine — wraps Hermes' AIAgent so Soma's async event loop can
delegate one turn at a time.

AIAgent.run_conversation() is synchronous. Soma is async (aiogram +
background curator). We bridge with asyncio.to_thread so a Hermes turn
blocks one worker thread, not the event loop.

One AIAgent instance lives for the bot's lifetime. Tools are fixed at
construction. Conversation history is owned by Soma and passed in on
each call — Hermes' own memory/context-files are disabled so Soma is
the single source of truth for what the model sees.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """Configuration for a SomaEngine instance.

    Anything not set falls back to environment variables — the same
    chain AIAgent uses (OPENROUTER_API_KEY, ANTHROPIC_API_KEY, ...).
    """

    model: str = ""
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_iterations: int = 30
    enabled_toolsets: Optional[List[str]] = None
    disabled_toolsets: Optional[List[str]] = None
    max_tokens: Optional[int] = None
    quiet: bool = True
    log_prefix: str = "[soma]"
    extra: Dict[str, Any] = field(default_factory=dict)


class SomaEngine:
    """Thin async-friendly wrapper around AIAgent.

    Usage:
        engine = SomaEngine(EngineConfig(model="..."))
        result = await engine.run_turn(
            user_message="hello",
            conversation_history=[],
            system_message="You are Soma.",
        )
        print(result["final_response"])
    """

    def __init__(self, config: EngineConfig, *, agent: Any = None):
        self.config = config
        if agent is not None:
            self._agent = agent
        else:
            self._agent = self._build_agent()

    def _build_agent(self):
        from run_agent import AIAgent

        return AIAgent(
            base_url=self.config.base_url,
            api_key=self.config.api_key or os.environ.get("OPENROUTER_API_KEY"),
            model=self.config.model,
            max_iterations=self.config.max_iterations,
            enabled_toolsets=self.config.enabled_toolsets,
            disabled_toolsets=self.config.disabled_toolsets,
            max_tokens=self.config.max_tokens,
            skip_context_files=True,
            skip_memory=True,
            save_trajectories=False,
            quiet_mode=self.config.quiet,
            log_prefix=self.config.log_prefix,
            **self.config.extra,
        )

    def run_turn_sync(
        self,
        user_message: str,
        *,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        system_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._agent.run_conversation(
            user_message=user_message,
            conversation_history=conversation_history or [],
            system_message=system_message,
        )

    async def run_turn(
        self,
        user_message: str,
        *,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        system_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await asyncio.to_thread(
            self.run_turn_sync,
            user_message,
            conversation_history=conversation_history,
            system_message=system_message,
        )
