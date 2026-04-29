"""
FusionPipeline - Level 14 Compression + BM25 Indexed Search.

A context engine that combines aggressive Level 14 compression (fires at 95%+ 
context utilization) with BM25 full-text search using SQLite FTS5.

Level 14 Compression:
    - threshold_percent=0.95 (fires at 95% of context length)
    - Uses iterative summarization like ContextCompressor
    - Maximum tail preservation for recent context

BM25 Index:
    - Leverages SessionDB's FTS5 virtual table for message search
    - Uses SQLite's native BM25 ranking (ORDER BY rank)
    - Supports FTS5 query syntax: keywords, phrases, boolean, prefix

Usage:
    from plugins.context_engine.fusion import FusionPipeline
    pipeline = FusionPipeline(model="claude-3-5-sonnet")
    pipeline.search("docker deployment")  # BM25 search
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from agent.context_compressor import ContextCompressor
from agent.context_engine import ContextEngine
from agent.model_metadata import MINIMUM_CONTEXT_LENGTH, get_model_context_length
from hermes_state import SessionDB

logger = logging.getLogger(__name__)

# Level 14 compression settings:
# - Fires at 95% context utilization (very late, maximizes context before compression)
# - More aggressive than default ContextCompressor (50%)
_LEVEL14_THRESHOLD_PERCENT = 0.95
_LEVEL14_PROTECT_LAST_N = 30  # Preserve more recent turns
_LEVEL14_SUMMARY_RATIO = 0.15  # Summary takes 15% of compressed content


class FusionPipeline(ContextEngine):
    """
    Context engine combining Level 14 aggressive compression with BM25 search.

    Level 14 Compression:
        - Fires when context reaches 95% of limit (vs 50% default)
        - Preserves last 30 messages / token budget for recent context
        - Iterative summarization for re-compression scenarios

    BM25 Search:
        - Uses SessionDB FTS5 for full-text message search
        - Native SQLite BM25 ranking
        - Supports: keywords, phrases, boolean operators, prefix matching
    """

    @property
    def name(self) -> str:
        return "fusion"

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        threshold_percent: float = _LEVEL14_THRESHOLD_PERCENT,
        protect_first_n: int = 3,
        protect_last_n: int = _LEVEL14_PROTECT_LAST_N,
        summary_target_ratio: float = _LEVEL14_SUMMARY_RATIO,
        quiet_mode: bool = False,
        summary_model_override: str = None,
        base_url: str = "",
        api_key: str = "",
        config_context_length: int | None = None,
        provider: str = "",
        api_mode: str = "",
        db_path: str = None,
    ):
        """
        Initialize FusionPipeline with Level 14 compression settings.

        Args:
            model: Model name for context length lookup
            threshold_percent: When to fire compression (0.95 = 95% for Level 14)
            protect_first_n: Number of head messages to always protect
            protect_last_n: Number of tail messages to always protect  
            summary_target_ratio: Portion of compressed content for summary
            quiet_mode: Suppress logging
            summary_model_override: Use different model for summarization
            base_url: API base URL for model context lookup
            api_key: API key for model context lookup
            config_context_length: Override context length
            provider: Model provider
            api_mode: API mode
            db_path: Optional custom path for SessionDB
        """
        # Delegate compression to ContextCompressor with Level 14 settings
        self._compressor = ContextCompressor(
            model=model,
            threshold_percent=threshold_percent,
            protect_first_n=protect_first_n,
            protect_last_n=protect_last_n,
            summary_target_ratio=summary_target_ratio,
            quiet_mode=quiet_mode,
            summary_model_override=summary_model_override,
            base_url=base_url,
            api_key=api_key,
            config_context_length=config_context_length,
            provider=provider,
            api_mode=api_mode,
        )

        # BM25 search via SessionDB
        self._session_db: Optional[SessionDB] = None
        self._db_path = db_path

    def _get_session_db(self) -> SessionDB:
        """Lazy initialization of SessionDB for BM25 search."""
        if self._session_db is None:
            if self._db_path:
                from pathlib import Path
                self._session_db = SessionDB(db_path=Path(self._db_path))
            else:
                self._session_db = SessionDB()
        return self._session_db

    # ── ContextEngine Interface ────────────────────────────────────────────────

    @property
    def last_prompt_tokens(self) -> int:
        return self._compressor.last_prompt_tokens

    @last_prompt_tokens.setter
    def last_prompt_tokens(self, value: int):
        self._compressor.last_prompt_tokens = value

    @property
    def last_completion_tokens(self) -> int:
        return self._compressor.last_completion_tokens

    @last_completion_tokens.setter
    def last_completion_tokens(self, value: int):
        self._compressor.last_completion_tokens = value

    @property
    def last_total_tokens(self) -> int:
        return self._compressor.last_total_tokens

    @last_total_tokens.setter
    def last_total_tokens(self, value: int):
        self._compressor.last_total_tokens = value

    @property
    def threshold_tokens(self) -> int:
        return self._compressor.threshold_tokens

    @property
    def context_length(self) -> int:
        return self._compressor.context_length

    @property
    def compression_count(self) -> int:
        return self._compressor.compression_count

    @property
    def threshold_percent(self) -> float:
        return self._compressor.threshold_percent

    @property
    def protect_first_n(self) -> int:
        return self._compressor.protect_first_n

    @property
    def protect_last_n(self) -> int:
        return self._compressor.protect_last_n

    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
        api_mode: str = "",
    ) -> None:
        self._compressor.update_model(
            model=model,
            context_length=context_length,
            base_url=base_url,
            api_key=api_key,
            provider=provider,
            api_mode=api_mode,
        )

    def on_session_start(self) -> None:
        self._compressor.on_session_start()

    def on_session_reset(self) -> None:
        self._compressor.on_session_reset()

    def on_session_end(self) -> None:
        self._compressor.on_session_end()
        if self._session_db:
            self._session_db.close()
            self._session_db = None

    def update_from_response(self, usage: Dict[str, Any]) -> None:
        self._compressor.update_from_response(usage)

    def should_compress(self, prompt_tokens: int = None) -> bool:
        return self._compressor.should_compress(prompt_tokens)

    def compress(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int = None,
        focus_topic: str = None,
    ) -> List[Dict[str, Any]]:
        """
        Compress conversation using Level 14 aggressive settings.
        
        Delegates to ContextCompressor with Level 14 threshold (95%).
        """
        return self._compressor.compress(messages, current_tokens, focus_topic)

    # ── BM25 Search Interface ──────────────────────────────────────────────────

    def search(
        self,
        query: str,
        source_filter: List[str] = None,
        exclude_sources: List[str] = None,
        role_filter: List[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Full-text search using BM25 ranking via SQLite FTS5.

        Uses SessionDB's FTS5 virtual table with native BM25 scoring.
        Results are ordered by SQLite's BM25 rank (lower = more relevant).

        Args:
            query: FTS5 query string. Supports:
                - Simple keywords: "docker deployment"
                - Phrases: '"exact phrase"'
                - Boolean: "docker OR kubernetes", "python NOT java"  
                - Prefix: "deploy*"
            source_filter: Only include these sources (e.g., ["cli", "telegram"])
            exclude_sources: Exclude these sources from results
            role_filter: Only include messages from these roles
            limit: Maximum results to return (default 20)
            offset: Skip first N results for pagination

        Returns:
            List of matching message dicts with:
                - id, session_id, role, content, timestamp
                - snippet: BM25-highlighted excerpt with >>>match<<< markers
                - tool_name, source, model, session_started
                - Additional context: 1 message before and after each match

        Example:
            >>> pipeline = FusionPipeline(model="claude-3-5-sonnet")
            >>> results = pipeline.search("docker kubernetes", limit=10)
            >>> for r in results:
            ...     print(f"{r['source']}: {r['snippet']}")
        """
        db = self._get_session_db()
        return db.search_messages(
            query=query,
            source_filter=source_filter,
            exclude_sources=exclude_sources,
            role_filter=role_filter,
            limit=limit,
            offset=offset,
        )

    def search_sessions(
        self,
        query: str,
        source_filter: List[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for sessions (not individual messages) matching the query.

        Useful for finding conversations about a topic without getting
        every matching message.

        Args:
            query: FTS5 query string
            source_filter: Filter by session source
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts with at least one matching message
        """
        # Get matching messages with their sessions
        matches = self.search(
            query=query,
            source_filter=source_filter,
            limit=limit * 3,  # Get more to deduplicate
            offset=0,
        )

        # Deduplicate by session_id, preserving best match per session
        session_map: Dict[str, Dict[str, Any]] = {}
        for match in matches:
            sid = match.get("session_id")
            if sid and sid not in session_map:
                session_map[sid] = {
                    "session_id": sid,
                    "source": match.get("source"),
                    "model": match.get("model"),
                    "started_at": match.get("session_started"),
                    "role": match.get("role"),
                    "snippet": match.get("snippet"),
                    "timestamp": match.get("timestamp"),
                }

        sessions = list(session_map.values())
        sessions.sort(key=lambda x: x.get("timestamp") or 0, reverse=True)
        return sessions[:limit]

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the BM25 index.

        Returns:
            Dict with index statistics:
                - total_messages: Total indexed messages
                - total_sessions: Total indexed sessions  
                - fts5_fts_version: FTS5 engine version
        """
        db = self._get_session_db()
        
        with db._lock:
            cursor = db._conn.execute(
                "SELECT COUNT(*) as cnt FROM messages_fts"
            )
            fts_count = cursor.fetchone()[0]

            cursor = db._conn.execute(
                "SELECT COUNT(*) as cnt FROM messages"
            )
            msg_count = cursor.fetchone()[0]

            cursor = db._conn.execute(
                "SELECT COUNT(*) as cnt FROM sessions" 
            )
            session_count = cursor.fetchone()[0]

        return {
            "indexed_messages": fts_count,
            "total_messages": msg_count,
            "total_sessions": session_count,
            "compression_level": 14,
            "threshold_percent": self.threshold_percent,
            "context_length": self.context_length,
            "compression_count": self.compression_count,
        }


# Plugin registration function
def register(ctx):
    """Plugin registration entry point."""
    ctx.register_context_engine(FusionPipeline())
