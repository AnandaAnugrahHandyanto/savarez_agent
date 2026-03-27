"""MindGraph memory provider for Hermes Agent.

Bridges the MindGraph semantic graph memory system into the MemoryProvider
interface. The heavy lifting (API calls, session management, proactive
retrieval) stays in tools/mindgraph_tool.py — this is a thin adapter.

Requires:
    - mindgraph-sdk (pip install mindgraph-sdk)
    - MINDGRAPH_API_KEY environment variable
"""

import logging
from typing import Optional

from memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


class MindGraphProvider(MemoryProvider):
    """MindGraph semantic graph memory provider.

    Provides:
    - Session context: active goals, open decisions, weak claims, policies
    - Turn context: score-gated semantic retrieval (proactive, per-turn)
    - Session lifecycle: auto-open/close with transcript ingestion
    """

    @property
    def name(self) -> str:
        return "mindgraph"

    def is_available(self) -> bool:
        """Check for mindgraph-sdk and MINDGRAPH_API_KEY."""
        try:
            from tools.mindgraph_tool import check_requirements
            return check_requirements()
        except ImportError:
            return False

    def on_session_start(self, session_id: str, label: str = "") -> None:
        """Open a MindGraph session for this conversation."""
        from tools.mindgraph_tool import auto_open_session
        session_label = label or f"hermes-{session_id[:8]}"
        sid = auto_open_session(label=session_label)
        if sid:
            logger.info("MindGraph session opened: %s", sid)

    def get_session_context(self) -> Optional[str]:
        """Retrieve goals, decisions, policies, etc. for the system prompt."""
        from tools.mindgraph_tool import retrieve_session_context
        return retrieve_session_context()

    def get_turn_context(self, user_message: str) -> Optional[str]:
        """Score-gated semantic retrieval for this user message."""
        from tools.mindgraph_tool import proactive_graph_retrieve
        return proactive_graph_retrieve(user_message)

    def on_session_end(self, summary: str = "",
                       transcript: list = None,
                       session_title: str = None) -> None:
        """Close the MindGraph session and ingest transcript."""
        from tools.mindgraph_tool import auto_close_session
        auto_close_session(
            summary=summary,
            transcript_messages=transcript,
            session_title=session_title,
        )
