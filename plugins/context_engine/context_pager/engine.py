"""ContextPagerEngine — Two-stage context compression engine.

Stage 1 — Semantic Dedup (lossless, zero cost):
  Hashes tool outputs (SHA-256), detects duplicates across turns in
  the same session, replaces repeats with stubs, and merges adjacent
  turns with identical tool signatures.  No LLM call, no information
  destroyed.

Stage 2 — Fallback ContextCompressor (lossy, paid):
  If Stage 1 dedup is insufficient and the result is still over the
  token threshold, fires the built-in ContextCompressor to summarise
  the remaining middle turns via the configured auxiliary model.
  Only fires when enabled (``fallback_compressor: true`` in config).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from agent.context_engine import ContextEngine
from agent.model_metadata import estimate_messages_tokens_rough

from .dedup import apply_dedup_compression, strip_annotations
from .store import SQLiteStore, OpenVikingArchiver

logger = logging.getLogger(__name__)


class ContextPagerEngine(ContextEngine):
    """Context engine that deduplicates tool outputs to reclaim context budget.

    This is a lossless compression strategy — no summarization, no
    information loss.  Identical tool outputs are replaced with stubs
    referencing the more recent occurrence.  Full originals are archived
    to OpenViking for potential future retrieval.
    """

    @property
    def name(self) -> str:
        return "context_pager"

    def __init__(
        self,
        protect_last_n: int = 6,
        protect_first_n: int = 3,
        threshold_percent: float = 0.75,
        sqlite_path: str | None = None,
        openviking_enabled: bool = True,
        context_length: int = 128_000,
        fallback_compressor: bool = False,
    ):
        self.protect_last_n = protect_last_n
        self.protect_first_n = protect_first_n
        self.threshold_percent = threshold_percent
        self.context_length = context_length
        self.threshold_tokens = int(context_length * threshold_percent)

        # Token tracking (required by run_agent.py)
        self.last_prompt_tokens = 0
        self.last_completion_tokens = 0
        self.last_total_tokens = 0
        self.compression_count = 0

        # Storage
        self._sqlite = SQLiteStore(db_path=sqlite_path)
        self._ov = OpenVikingArchiver() if openviking_enabled else None

        # Session state
        self._session_id: str = ""
        self._lock = threading.Lock()

        # Fallback LLM compressor (Stage 2)
        self._fallback_compressor_enabled = fallback_compressor
        self._fallback_compressor = None  # lazy-constructed
        self._model = ""
        self._base_url = ""
        self._api_key = ""
        self._provider = ""

        logger.info(
            "ContextPagerEngine initialized: protect_first=%d protect_last=%d "
            "threshold=%.0f%% context=%d ov=%s fallback=%s",
            protect_first_n, protect_last_n,
            threshold_percent * 100, context_length,
            "enabled" if openviking_enabled else "disabled",
            "enabled" if fallback_compressor else "disabled",
        )

    # ------------------------------------------------------------------
    # Model tracking (required for fallback compressor)
    # ------------------------------------------------------------------

    def update_model(
        self,
        model: str,
        context_length: int,
        base_url: str = "",
        api_key: str = "",
        provider: str = "",
        api_mode: str = "",
    ) -> None:
        """Capture model info and (re)create fallback compressor if enabled."""
        super().update_model(model, context_length, base_url, api_key, provider, api_mode)
        self._model = model
        self._base_url = base_url
        self._api_key = api_key
        self._provider = provider
        if self._fallback_compressor_enabled:
            self._init_fallback_compressor()

    def _init_fallback_compressor(self) -> None:
        """Lazy-construct the built-in ContextCompressor as Stage 2."""
        from agent.context_compressor import ContextCompressor
        self._fallback_compressor = ContextCompressor(
            model=self._model or "unknown",
            quiet_mode=True,
            config_context_length=self.context_length,
            protect_first_n=self.protect_first_n,
            protect_last_n=self.protect_last_n,
            provider=self._provider,
            base_url=self._base_url,
            api_key=self._api_key,
        )
        logger.info("Fallback compressor initialized (model=%s)", self._model or "unknown")

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def update_from_response(self, usage: Dict[str, Any]) -> None:
        """Update tracked token usage from an API response."""
        self.last_prompt_tokens = usage.get("prompt_tokens", 0)
        self.last_completion_tokens = usage.get("completion_tokens", 0)
        self.last_total_tokens = usage.get(
            "total_tokens",
            self.last_prompt_tokens + self.last_completion_tokens,
        )

    def should_compress(self, prompt_tokens: int | None = None) -> bool:
        """Return True if the current prompt exceeds the threshold."""
        tokens = prompt_tokens if prompt_tokens is not None else self.last_prompt_tokens
        if tokens <= 0:
            return False
        return tokens > self.threshold_tokens

    def has_content_to_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """Quick check: is there anything that can be compressed?

        Returns True if there are at least protect_first_n + protect_last_n + 2
        messages (system + head + at least 1 middle message).
        """
        non_system = [m for m in messages if m.get("role") != "system"]
        return len(non_system) > (self.protect_first_n + self.protect_last_n)

    def compress(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int | None = None,
        focus_topic: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Compact the message list via semantic dedup and merging.

        Algorithm:
        1. Guard: if not enough messages, return unchanged.
        2. Annotate messages with turn indices.
        3. Compute head (protected first N) and tail (protected last N).
        4. For tool outputs in the middle window, check if they duplicate
           more recent tool outputs via SHA-256 hash lookup.
        5. Replace duplicates with stubs referencing the more recent turn.
        6. Merge adjacent turns with identical tool signatures.
        7. Validate role alternation.
        8. Archive originals to OpenViking (best-effort).
        9. Store new hashes from the middle window.
        10. Return the compressed list.
        """
        with self._lock:
            return self._compress_impl(messages, current_tokens, focus_topic)

    def _compress_impl(
        self,
        messages: List[Dict[str, Any]],
        current_tokens: int | None = None,
        focus_topic: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Internal compress implementation (under lock)."""

        # --- Guard: not enough messages to bother ---
        if not messages:
            return []
        non_system = [m for m in messages if m.get("role") != "system"]
        if len(non_system) <= (self.protect_first_n + self.protect_last_n):
            logger.debug(
                "compress: only %d non-system messages (need > %d) — skipping",
                len(non_system),
                self.protect_first_n + self.protect_last_n,
            )
            return list(messages)

        # --- Apply dedup compression ---
        session_id = self._session_id or "default"

        def hash_lookup_fn(content_hash: str, older_than_turn: int) -> List[Dict[str, Any]]:
            return self._sqlite.find_tool_duplicates(
                session_id, content_hash, older_than_turn,
            )

        try:
            compressed, middle_originals = apply_dedup_compression(
                messages,
                self.protect_first_n,
                self.protect_last_n,
                hash_lookup_fn,
            )
        except Exception as exc:
            logger.warning("compress: dedup compression failed: %s", exc)
            return list(messages)

        # --- Stage 2: Fallback LLM compressor (if enabled and still over threshold) ---
        if self._fallback_compressor and self._fallback_compressor_enabled:
            try:
                post_dedup_tokens = estimate_messages_tokens_rough(compressed)
                if self.should_compress(post_dedup_tokens):
                    logger.info(
                        "compress: post-dedup estimate %d tokens exceeds threshold %d — "
                        "firing fallback compressor",
                        post_dedup_tokens, self.threshold_tokens,
                    )
                    compressed = self._fallback_compressor.compress(compressed)
                    # Stage 2 replaced the messages — skip hash storage (stale)
                    # and OV archival (already embedded in summary)
                    self.compression_count += 1
                    return compressed
            except Exception as exc:
                logger.warning("compress: fallback compressor failed: %s", exc)
                # Fall through — return Stage 1 result

        # --- Store new hashes from the middle window ---
        try:
            self._store_middle_hashes(messages, session_id)
        except Exception as exc:
            logger.debug("compress: hash storage failed (non-fatal): %s", exc)

        # --- Archive originals to OpenViking (best-effort) ---
        if self._ov and middle_originals:
            try:
                # Extract turn indices from the original messages
                from .dedup import extract_turns
                annotated_originals = extract_turns(messages)
                middle_start = 0
                # Find where middle starts
                for i, m in enumerate(annotated_originals):
                    if m.get("_turn_index", -1) >= self.protect_first_n:
                        middle_start = i
                        break
                # Archive each turn in the middle window
                turn_groups: Dict[int, List[Dict[str, Any]]] = {}
                for i, m in enumerate(annotated_originals[middle_start:]):
                    ti = m.get("_turn_index", -1)
                    if ti >= 0:
                        turn_groups.setdefault(ti, []).append(
                            {k: v for k, v in m.items() if not k.startswith("_")}
                        )
                for ti, turn_msgs in turn_groups.items():
                    self._ov.archive_turn(session_id, ti, turn_msgs)
            except Exception as exc:
                logger.debug("compress: OV archival failed (non-fatal): %s", exc)

        # --- Update tracking ---
        self.compression_count += 1

        original_len = len(messages)
        new_len = len(compressed)
        if new_len < original_len:
            logger.info(
                "compress: %d → %d messages (%d saved, %.0f%%)",
                original_len, new_len,
                original_len - new_len,
                (1 - new_len / max(original_len, 1)) * 100,
            )
        else:
            logger.debug(
                "compress: no messages removed (%d → %d)",
                original_len, new_len,
            )

        return compressed

    def _store_middle_hashes(
        self,
        messages: List[Dict[str, Any]],
        session_id: str,
    ) -> None:
        """Store hashes for tool outputs in the middle window."""
        from .dedup import extract_turns, hash_tool_content

        annotated = extract_turns(messages)
        non_system = [m for m in annotated if m.get("_turn_index", -1) >= 0]
        if not non_system:
            return

        # Compute actual turn count (not message count)
        try:
            max_turn = max(m.get("_turn_index", -1) for m in non_system)
            total_turns = max_turn + 1 if max_turn >= 0 else 0
        except ValueError:
            total_turns = 0

        if total_turns == 0:
            return

        first_protected_turns = min(self.protect_first_n, total_turns)
        last_protected_turns = min(
            self.protect_last_n,
            max(0, total_turns - first_protected_turns),
        )

        middle_start_turn = first_protected_turns
        middle_end_turn = total_turns - last_protected_turns - 1

        if middle_start_turn > middle_end_turn:
            return

        for msg_idx, msg in enumerate(annotated):
            ti: int = msg.get("_turn_index") or 0
            if ti < middle_start_turn or ti > middle_end_turn:
                continue
            if msg.get("role") != "tool":
                continue
            content = msg.get("content", "")
            if not content:
                continue
            content_hash = hash_tool_content(content)
            self._sqlite.store_tool_hash(
                session_id=session_id,
                turn_index=ti,
                msg_index=msg_idx,
                content_hash=content_hash,
                content=str(content),
                tool_name=msg.get("name", ""),
            )

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    def on_session_start(self, session_id: str, **kwargs) -> None:
        """Initialize per-session state."""
        with self._lock:
            self._session_id = session_id
            if self._ov:
                self._ov.is_available()  # probe health

        logger.debug("ContextPager: session started: %s", session_id)

    def on_session_end(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        """Finalize session — close SQLite store."""
        with self._lock:
            if session_id and session_id == self._session_id:
                self._store_session_metadata(session_id, messages)
            self._sqlite.close()
            self._session_id = ""

        logger.debug("ContextPager: session ended: %s", session_id)

    def on_session_reset(self) -> None:
        """Reset per-session state (no persistent data deleted)."""
        super().on_session_reset()
        with self._lock:
            self._session_id = ""

        logger.debug("ContextPager: session reset")

    def _store_session_metadata(
        self, session_id: str, messages: List[Dict[str, Any]]
    ) -> None:
        """Store final session metadata."""
        non_system = [m for m in messages if m.get("role") != "system"]
        from .dedup import extract_turns
        annotated = extract_turns(messages)
        unique_turns = len({
            m.get("_turn_index", -1)
            for m in annotated
            if m.get("_turn_index", -1) >= 0
        })
        self._sqlite.store_session_metadata(
            session_id=session_id,
            turn_count=unique_turns,
            metadata={
                "total_messages": len(messages),
                "non_system_messages": len(non_system),
                "compression_count": self.compression_count,
            },
        )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return status dict for display/logging."""
        status = super().get_status()
        status["protect_first_n"] = self.protect_first_n
        status["protect_last_n"] = self.protect_last_n
        status["ov_available"] = self._ov.is_available() if self._ov else False
        return status
