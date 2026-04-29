"""
WikiBuilder — LLM-Wiki-style incremental knowledge base builder.

Inspired by Karpathy's LLM Wiki and nashsu/llm_wiki patterns:
  - Facts are extracted incrementally from conversation
  - Related facts are linked into a knowledge network
  - Each "page" is a compound knowledge node with provenance tracking
  - Periodic consolidation merges similar entries

Key concepts:
  - WikiPage: A named topic with content, links to other pages, and confidence
  - Link: Directed connection between pages with relation type
  - Consolidation: Periodic merge of similar/related pages
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from hermes_constants import get_hermes_home

logger = logging.getLogger(__name__)

DEFAULT_WIKI_DB_PATH = get_hermes_home() / "wiki.db"

# -----------------------------------------------------------------------------
# Schema
# -----------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS wiki_pages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    title_normalized TEXT NOT NULL,
    content         TEXT NOT NULL DEFAULT '',
    summary         TEXT NOT NULL DEFAULT '',
    page_type       TEXT NOT NULL DEFAULT 'topic',
    confidence      REAL NOT NULL DEFAULT 0.5,
    source_sessions TEXT NOT NULL DEFAULT '[]',
    source_turns    TEXT NOT NULL DEFAULT '[]',
    tags            TEXT NOT NULL DEFAULT '[]',
    links           TEXT NOT NULL DEFAULT '[]',  -- JSON list of {target_id, rel_type}
    access_count    INTEGER NOT NULL DEFAULT 0,
    last_accessed   REAL NOT NULL,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL,
    UNIQUE(title_normalized)
);

CREATE INDEX IF NOT EXISTS idx_wiki_title_norm ON wiki_pages(title_normalized);
CREATE INDEX IF NOT EXISTS idx_wiki_page_type ON wiki_pages(page_type);
CREATE INDEX IF NOT EXISTS idx_wiki_last_access ON wiki_pages(last_accessed DESC);

CREATE TABLE IF NOT EXISTS wiki_relations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    from_page_id    INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    to_page_id      INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    relation_type   TEXT NOT NULL,
    context         TEXT NOT NULL DEFAULT '',
    confidence      REAL NOT NULL DEFAULT 0.5,
    source_session  TEXT,
    created_at      REAL NOT NULL,
    UNIQUE(from_page_id, to_page_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_wiki_rel_from ON wiki_relations(from_page_id);
CREATE INDEX IF NOT EXISTS idx_wiki_rel_to ON wiki_relations(to_page_id);

CREATE TABLE IF NOT EXISTS wiki_extraction_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    turn            INTEGER NOT NULL,
    extracted_content TEXT NOT NULL,
    page_ids        TEXT NOT NULL DEFAULT '[]',
    created_at      REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wiki_log_session ON wiki_extraction_log(session_id);
"""

# Relation types
REL_SIMILAR = "similar_to"
REL_PART_OF = "part_of"
REL_DEPENDS = "depends_on"
REL_USES = "uses"
REL_CONTRADICTS = "contradicts"
REL_RELATED = "related_to"


# -----------------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------------

@dataclass
class WikiPage:
    id: Optional[int] = None
    title: str = ""
    content: str = ""
    summary: str = ""
    page_type: str = "topic"
    confidence: float = 0.5
    source_sessions: List[str] = field(default_factory=list)
    source_turns: List[int] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)  # [{target_id, rel_type}]
    access_count: int = 0
    last_accessed: float = 0.0
    created_at: float = 0.0
    updated_at: float = 0.0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WikiPage":
        return cls(
            id=row["id"],
            title=row["title"],
            content=row["content"],
            summary=row["summary"],
            page_type=row["page_type"],
            confidence=row["confidence"],
            source_sessions=json.loads(row["source_sessions"]),
            source_turns=json.loads(row["source_turns"]),
            tags=json.loads(row["tags"]),
            links=json.loads(row["links"]),
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "page_type": self.page_type,
            "confidence": self.confidence,
            "source_sessions": self.source_sessions,
            "source_turns": self.source_turns,
            "tags": self.tags,
            "links": self.links,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# -----------------------------------------------------------------------------
# WikiBuilder
# -----------------------------------------------------------------------------

class WikiBuilder:
    """
    Incremental wiki-style knowledge base builder.

    Builds a compound knowledge wiki from conversation content:
      - Extracts key topics and facts from each turn
      - Links related pages into a knowledge network
      - Consolidates similar pages periodically
      - Tracks provenance (which session/turn each fact came from)
    """

    def __init__(
        self,
        db_path: Path | None = None,
        kg: Any = None,    # KnowledgeGraph reference
        max_pages: int = 5000,
        redact_func: Callable[[str], str] | None = None,
    ):
        self.db_path = Path(db_path) if db_path else DEFAULT_WIKI_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.kg = kg
        self.max_pages = max_pages
        self.redact_func = redact_func or (lambda x: x)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()

    # -------------------------------------------------------------------------
    # Page operations
    # -------------------------------------------------------------------------

    def upsert_page(
        self,
        title: str,
        content: str = "",
        summary: str = "",
        page_type: str = "topic",
        confidence: float = 0.5,
        source_session: str = "",
        source_turn: int = 0,
        tags: List[str] | None = None,
    ) -> WikiPage:
        """Create or update a wiki page."""
        clean_title = self.redact_func(title)
        clean_content = self.redact_func(content)
        clean_summary = self.redact_func(summary)
        title_norm = self._normalize_title(clean_title)
        tags = tags or []
        now = time.time()

        with self._lock:
            cur = self._conn.cursor()

            # Check if exists
            cur.execute(
                "SELECT * FROM wiki_pages WHERE title_normalized = ?",
                (title_norm,),
            )
            existing = cur.fetchone()

            if existing:
                page = WikiPage.from_row(existing)
                # Update
                new_sessions = list(set(page.source_sessions + [source_session]))
                new_turns = list(set(page.source_turns + [source_turn]))

                cur.execute(
                    """
                    UPDATE wiki_pages
                    SET content=?, summary=?, page_type=?,
                        confidence=?, source_sessions=?, source_turns=?,
                        tags=?, updated_at=?
                    WHERE id = ?
                    """,
                    (
                        clean_content, clean_summary, page_type,
                        confidence, json.dumps(new_sessions),
                        json.dumps(new_turns), json.dumps(tags),
                        now, page.id,
                    ),
                )
                page_id = page.id
            else:
                cur.execute(
                    """
                    INSERT INTO wiki_pages
                        (title, title_normalized, content, summary, page_type,
                         confidence, source_sessions, source_turns, tags,
                         access_count, last_accessed, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
                    """,
                    (
                        clean_title, title_norm, clean_content, clean_summary,
                        page_type, confidence, json.dumps([source_session]),
                        json.dumps([source_turn]), json.dumps(tags),
                        now, now, now,
                    ),
                )
                page_id = cur.lastrowid

            self._conn.commit()

            # Fetch and return
            cur.execute("SELECT * FROM wiki_pages WHERE id = ?", (page_id,))
            return WikiPage.from_row(cur.fetchone())

    def get_page(self, page_id: int) -> Optional[WikiPage]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT * FROM wiki_pages WHERE id = ?", (page_id,))
            row = cur.fetchone()
            return WikiPage.from_row(row) if row else None

    def get_page_by_title(self, title: str) -> Optional[WikiPage]:
        norm = self._normalize_title(title)
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM wiki_pages WHERE title_normalized = ?",
                (norm,),
            )
            row = cur.fetchone()
            return WikiPage.from_row(row) if row else None

    def search_pages(
        self,
        query: str,
        page_type: str = "",
        tags: List[str] | None = None,
        limit: int = 20,
    ) -> List[WikiPage]:
        """Search wiki pages by title/content."""
        with self._lock:
            cur = self._conn.cursor()
            if page_type:
                cur.execute(
                    """
                    SELECT * FROM wiki_pages
                    WHERE page_type = ?
                    ORDER BY last_accessed DESC
                    LIMIT ?
                    """,
                    (page_type, limit),
                )
            else:
                cur.execute(
                    """
                    SELECT * FROM wiki_pages
                    ORDER BY last_accessed DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            pages = [WikiPage.from_row(row) for row in cur.fetchall()]

        # Filter by query in title/content
        if query:
            query_lower = query.lower()
            pages = [
                p for p in pages
                if query_lower in p.title.lower() or query_lower in p.content.lower()
            ][:limit]

        if tags:
            tags_lower = {t.lower() for t in tags}
            pages = [
                p for p in pages
                if tags_lower & {t.lower() for t in p.tags}
            ][:limit]

        return pages

    def add_link(
        self,
        from_page_id: int,
        to_page_id: int,
        relation_type: str = REL_RELATED,
        context: str = "",
        confidence: float = 0.5,
        source_session: str = "",
    ) -> bool:
        """Add a link between two wiki pages."""
        if from_page_id == to_page_id:
            return False

        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO wiki_relations
                    (from_page_id, to_page_id, relation_type, context,
                     confidence, source_session, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (from_page_id, to_page_id, relation_type, context,
                 confidence, source_session, time.time()),
            )
            self._conn.commit()
            return cur.rowcount > 0

    def get_page_links(self, page_id: int) -> List[Tuple[WikiPage, str]]:
        """Get all pages linked from this page with relation types."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT p.*, r.relation_type
                FROM wiki_relations r
                JOIN wiki_pages p ON p.id = r.to_page_id
                WHERE r.from_page_id = ?
                ORDER BY r.relation_type
                """,
                (page_id,),
            )
            return [
                (WikiPage.from_row(row), row["relation_type"])
                for row in cur.fetchall()
            ]

    def touch_page(self, page_id: int) -> None:
        """Update last_accessed time."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE wiki_pages
                SET access_count = access_count + 1, last_accessed = ?
                WHERE id = ?
                """,
                (time.time(), page_id),
            )
            self._conn.commit()

    # -------------------------------------------------------------------------
    # Extraction pipeline
    # -------------------------------------------------------------------------

    def process_content(
        self,
        session_id: str,
        turn: int,
        content: str,
        extract_func: Callable[[str], Any] | None = None,
        entity_extractor: Any = None,
    ) -> List[int]:
        """
        Extract wiki pages from conversation content.

        Returns list of created/updated page IDs.
        """
        clean_content = self.redact_func(content)
        page_ids: List[int] = []

        # Extract facts using the provided function or entity extractor
        if extract_func:
            extracted = extract_func(clean_content)
        elif entity_extractor:
            extracted = entity_extractor.extract(clean_content)
        else:
            extracted = self._default_extract(clean_content)

        topics = extracted.get("topics", [])
        facts = extracted.get("facts", [])
        relations = extracted.get("relations", [])

        # Create/update topic pages
        for topic in topics:
            title = topic.get("title", "")
            if not title:
                continue
            page = self.upsert_page(
                title=title,
                content=topic.get("content", ""),
                summary=topic.get("summary", ""),
                page_type=topic.get("type", "topic"),
                confidence=topic.get("confidence", 0.6),
                source_session=session_id,
                source_turn=turn,
                tags=topic.get("tags", []),
            )
            page_ids.append(page.id)

        # Create fact pages
        for fact in facts:
            content_text = fact.get("content", "")
            if not content_text:
                continue
            page = self.upsert_page(
                title=content_text[:80],  # Use first 80 chars as title
                content=content_text,
                summary=content_text[:200],
                page_type="fact",
                confidence=fact.get("confidence", 0.7),
                source_session=session_id,
                source_turn=turn,
                tags=["auto-generated"],
            )
            page_ids.append(page.id)

        # Add relations
        for rel in relations:
            from_title = rel.get("from", "")
            to_title = rel.get("to", "")
            rel_type = rel.get("type", REL_RELATED)
            if not from_title or not to_title:
                continue

            from_page = self.get_page_by_title(from_title)
            to_page = self.get_page_by_title(to_title)
            if from_page and to_page:
                self.add_link(
                    from_page.id, to_page.id, rel_type,
                    context=rel.get("context", ""),
                    confidence=rel.get("confidence", 0.5),
                    source_session=session_id,
                )

        # Log extraction
        self._log_extraction(session_id, turn, clean_content, page_ids)

        return page_ids

    def _log_extraction(
        self,
        session_id: str,
        turn: int,
        content: str,
        page_ids: List[int],
    ) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO wiki_extraction_log
                    (session_id, turn, extracted_content, page_ids, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, turn, content[:5000], json.dumps(page_ids), time.time()),
            )
            self._conn.commit()

    def _default_extract(self, content: str) -> Dict[str, Any]:
        """Simple default extraction — split content into sentences."""
        sentences = re.split(r"[.!\n]+", content)
        facts = [
            {"content": s.strip(), "confidence": 0.5}
            for s in sentences
            if len(s.strip()) > 20 and len(s.strip()) < 500
        ]
        return {"topics": [], "facts": facts, "relations": []}

    # -------------------------------------------------------------------------
    # Consolidation
    # -------------------------------------------------------------------------

    def consolidate_similar_pages(self, similarity_threshold: float = 0.8) -> int:
        """
        Find and merge pages with very similar content.

        Returns number of pages merged.
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM wiki_pages WHERE page_type = 'fact' ORDER BY created_at DESC"
            )
            pages = [WikiPage.from_row(row) for row in cur.fetchall()]

        merged_count = 0
        to_delete: Set[int] = set()

        for i, page_a in enumerate(pages):
            if page_a.id in to_delete:
                continue
            for page_b in pages[i + 1:]:
                if page_b.id in to_delete:
                    continue

                # Simple similarity: content overlap ratio
                if self._content_similarity(page_a.content, page_b.content) >= similarity_threshold:
                    # Merge into the newer page
                    newer = page_b if page_b.created_at > page_a.created_at else page_a
                    older = page_a if newer is page_b else page_b

                    self.upsert_page(
                        title=newer.title,
                        content=newer.content,
                        summary=newer.summary,
                        page_type=newer.page_type,
                        confidence=max(newer.confidence, older.confidence),
                        source_session=",".join(
                            filter(None, [
                                ",".join(newer.source_sessions),
                                ",".join(older.source_sessions),
                            ])
                        ),
                        source_turn=max(
                            max(newer.source_turns) if newer.source_turns else 0,
                            max(older.source_turns) if older.source_turns else 0,
                        ),
                        tags=list(set(newer.tags + older.tags)),
                    )

                    to_delete.add(older.id)
                    merged_count += 1

        # Delete merged pages
        if to_delete:
            with self._lock:
                cur = self._conn.cursor()
                for pid in to_delete:
                    cur.execute("DELETE FROM wiki_pages WHERE id = ?", (pid,))
                self._conn.commit()

        if merged_count:
            logger.info("Consolidated %d duplicate wiki pages", merged_count)
        return merged_count

    def _content_similarity(self, text_a: str, text_b: str) -> float:
        """Compute simple word-overlap similarity between two texts."""
        words_a = set(re.findall(r"\w+", text_a.lower()))
        words_b = set(re.findall(r"\w+", text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    # -------------------------------------------------------------------------
    # Auto-linking
    # -------------------------------------------------------------------------

    def auto_link_pages(self) -> int:
        """
        Automatically create links between pages based on content similarity.

        Returns number of new links created.
        """
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT * FROM wiki_pages WHERE page_type = 'topic' ORDER BY updated_at DESC LIMIT 200"
            )
            pages = [WikiPage.from_row(row) for row in cur.fetchall()]

        links_created = 0
        for page in pages:
            if not page.id:
                continue

            # Find related pages by keyword overlap
            page_words = set(re.findall(r"\w+", page.title.lower() + " " + page.content.lower()))

            for other in pages:
                if other.id == page.id:
                    continue

                # Check if any significant word overlaps
                other_words = set(re.findall(r"\w+", other.title.lower() + " " + other.content.lower()))
                overlap = page_words & other_words
                if len(overlap) >= 3:  # At least 3 shared significant words
                    if self.add_link(
                        page.id, other.id, REL_RELATED,
                        context=f"Auto-linked: shared terms {overlap}",
                        confidence=0.4,
                    ):
                        links_created += 1

        return links_created

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_title(title: str) -> str:
        """Normalize a title for uniqueness comparison."""
        return re.sub(r"[^\w]", "", title.lower()).strip()

    def page_count(self) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM wiki_pages")
            return cur.fetchone()[0]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM wiki_pages")
            page_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM wiki_relations")
            rel_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM wiki_extraction_log")
            log_count = cur.fetchone()[0]
        return {
            "pages": page_count,
            "relations": rel_count,
            "extractions": log_count,
            "db_path": str(self.db_path),
        }

    def close(self) -> None:
        with self._lock:
            self._conn.close()
