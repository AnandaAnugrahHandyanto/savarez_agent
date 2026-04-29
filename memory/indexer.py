"""
IncrementalIndexer — background indexer that processes new content without full rebuild.

Key design:
  - Content is queued and processed asynchronously (threading)
  - Each session's new content is tracked via a cursor
  - Merge/dedup happens periodically, not on every write
  - Configurable interval for merge operations
"""

from __future__ import annotations

import atexit
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Index queue item
# -----------------------------------------------------------------------------

@dataclass
class IndexItem:
    """A single item to be indexed."""
    session_id: str
    turn_number: int
    content: str
    content_type: str = "text"   # "text" | "entity" | "fact"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0            # higher = processed first


# -----------------------------------------------------------------------------
# IncrementalIndexer
# -----------------------------------------------------------------------------

class IncrementalIndexer:
    """
    Background indexer that processes new content incrementally.

    Usage:
        indexer = IncrementalIndexer(kg=knowledge_graph, retriever=retriever)
        indexer.start()

        # In the agent loop:
        indexer.queue(session_id, turn_number, content)

        # At shutdown:
        indexer.stop()
    """

    def __init__(
        self,
        kg: Any,            # KnowledgeGraph instance
        retriever: Any,     # Retriever instance
        entity_extractor: Any,  # EntityExtractor instance
        index_interval: float = 60.0,   # merge interval in seconds
        batch_size: int = 50,
        max_queue_size: int = 1000,
        redact_func: Callable[[str], str] | None = None,
    ):
        self.kg = kg
        self.retriever = retriever
        self.entity_extractor = entity_extractor
        self.index_interval = index_interval
        self.batch_size = batch_size
        self.max_queue_size = max_queue_size
        self.redact_func = redact_func or (lambda x: x)

        self._queue: deque[IndexItem] = deque()
        self._lock = threading.RLock()
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._paused.set()  # Start unpaused
        self._last_merge_time = time.time()
        self._session_cursors: Dict[str, int] = {}  # session_id → last processed turn
        self._stats = {
            "items_indexed": 0,
            "entities_created": 0,
            "relations_created": 0,
            "merges_done": 0,
        }

        # Register cleanup
        atexit.register(self.stop)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Start the background indexing thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self._worker_thread.start()
        logger.info("IncrementalIndexer started (interval=%.1fs, batch=%d)",
                    self.index_interval, self.batch_size)

    def stop(self) -> None:
        """Stop the background thread and flush remaining items."""
        if self._worker_thread is None:
            return
        self._stop_event.set()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
        self._flush()
        logger.info("IncrementalIndexer stopped (stats=%s)", self._stats)

    def pause(self) -> None:
        """Pause indexing (e.g., during bulk operations)."""
        self._paused.clear()

    def resume(self) -> None:
        """Resume indexing."""
        self._paused.set()

    # -------------------------------------------------------------------------
    # Queue management
    # -------------------------------------------------------------------------

    def queue(
        self,
        session_id: str,
        turn_number: int,
        content: str,
        content_type: str = "text",
        metadata: Dict[str, Any] | None = None,
        priority: int = 0,
    ) -> None:
        """
        Queue content for indexing.

        This is non-blocking — returns immediately.
        """
        # Redact sensitive content before queuing
        clean_content = self.redact_func(content)

        item = IndexItem(
            session_id=session_id,
            turn_number=turn_number,
            content=clean_content,
            content_type=content_type,
            metadata=metadata or {},
            priority=priority,
        )

        with self._lock:
            if len(self._queue) >= self.max_queue_size:
                # Drop oldest low-priority items
                dropped = 0
                while self._queue and len(self._queue) >= self.max_queue_size:
                    oldest = self._queue.popleft()
                    if oldest.priority < priority:
                        dropped += 1
                if dropped:
                    logger.warning("Dropped %d old queue items due to overflow", dropped)

            self._queue.append(item)

    def queue_entity(
        self,
        session_id: str,
        turn_number: int,
        entity_data: Dict[str, Any],
    ) -> None:
        """Queue a pre-extracted entity for indexing."""
        self.queue(
            session_id=session_id,
            turn_number=turn_number,
            content=entity_data.get("name", ""),
            content_type="entity",
            metadata={"entity_data": entity_data},
            priority=5,
        )

    def queue_relation(
        self,
        session_id: str,
        turn_number: int,
        relation_data: Dict[str, Any],
    ) -> None:
        """Queue a pre-extracted relation for indexing."""
        self.queue(
            session_id=session_id,
            turn_number=turn_number,
            content=f"{relation_data.get('from_name', '')} --{relation_data.get('relation_type', '')}--> {relation_data.get('to_name', '')}",
            content_type="relation",
            metadata={"relation_data": relation_data},
            priority=5,
        )

    # -------------------------------------------------------------------------
    # Background worker
    # -------------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main worker loop."""
        while not self._stop_event.is_set():
            self._paused.wait(timeout=0.5)  # Check every 500ms

            if self._stop_event.is_set():
                break

            # Check if we should do a periodic merge
            now = time.time()
            if now - self._last_merge_time >= self.index_interval:
                self._merge()
                self._last_merge_time = now

            # Process batch from queue
            self._process_batch()

    def _process_batch(self) -> None:
        """Process a batch of items from the queue."""
        batch: List[IndexItem] = []

        with self._lock:
            for _ in range(min(self.batch_size, len(self._queue))):
                if self._queue:
                    batch.append(self._queue.popleft())

        if not batch:
            return

        for item in batch:
            self._index_item(item)

    def _index_item(self, item: IndexItem) -> None:
        """Index a single item."""
        try:
            if item.content_type == "entity":
                entity_data = item.metadata.get("entity_data", {})
                self.kg.bulk_upsert_entities(
                    [entity_data],
                    source_session=item.session_id,
                )
                self._stats["entities_created"] += 1

            elif item.content_type == "relation":
                rel_data = item.metadata.get("relation_data", {})
                self.kg.bulk_upsert_relations(
                    [rel_data],
                    source_session=item.session_id,
                )
                self._stats["relations_created"] += 1

            elif item.content_type == "text":
                # Run entity extraction
                extraction = self.entity_extractor.extract(item.content)

                if extraction.entities:
                    self.kg.bulk_upsert_entities(
                        extraction.entities,
                        source_session=item.session_id,
                    )
                    self._stats["entities_created"] += len(extraction.entities)

                if extraction.relations:
                    self.kg.bulk_upsert_relations(
                        extraction.relations,
                        source_session=item.session_id,
                    )
                    self._stats["relations_created"] += len(extraction.relations)

                # Also index the text itself for retrieval
                if item.content:
                    entity_ids = [
                        e["id"]
                        for e in extraction.entities
                        if e.get("id") is not None
                    ]
                    self.retriever.index_documents(
                        [item.content],
                        metadata=[{"session_id": item.session_id, "turn": item.turn_number}],
                        doc_ids=[-1] * 1,
                    )

                # Index free-text facts
                for fact in extraction.facts:
                    self.retriever.index_documents(
                        [fact],
                        metadata=[{"session_id": item.session_id, "type": "fact"}],
                        doc_ids=[-1],
                    )

            # Update cursor
            self._session_cursors[item.session_id] = max(
                self._session_cursors.get(item.session_id, 0),
                item.turn_number,
            )

            self._stats["items_indexed"] += 1

        except Exception as exc:
            logger.warning("Failed to index item (session=%s turn=%d): %s",
                           item.session_id, item.turn_number, exc)

    def _merge(self) -> None:
        """
        Periodic merge/dedup operation.

        Currently:
          - Rebuilds the entity FTS index for consistency
          - Triggers a VACUUM if the DB is large
        """
        if not self.kg:
            return

        try:
            entity_count = self.kg.entity_count()
            if entity_count > 5000:
                self.kg.vacuum()
                logger.info("Knowledge graph merge complete (entities=%d)", entity_count)
            self._stats["merges_done"] += 1
        except Exception as exc:
            logger.warning("Merge failed: %s", exc)

    def _flush(self) -> None:
        """Process all remaining items in the queue."""
        while True:
            batch: List[IndexItem] = []
            with self._lock:
                for _ in range(min(self.batch_size, len(self._queue))):
                    if self._queue:
                        batch.append(self._queue.popleft())
                if not batch:
                    break

            for item in batch:
                self._index_item(item)

    # -------------------------------------------------------------------------
    # Stats and monitoring
    # -------------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Return indexing statistics."""
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "session_cursors": dict(self._session_cursors),
        }

    @property
    def is_running(self) -> bool:
        return self._worker_thread is not None and self._worker_thread.is_alive()

    @property
    def pending_items(self) -> int:
        return len(self._queue)
