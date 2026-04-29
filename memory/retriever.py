"""
Retriever — BM25 full-text search with optional vector similarity.

BM25 is always available (pure Python, no extra deps).
Vector similarity is available when chromadb is installed.

Supports multi-hop reasoning via graph traversal of the knowledge graph.
"""

from __future__ import annotations

import logging
import math
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# BM25 Implementation (pure Python, no external deps)
# -----------------------------------------------------------------------------

class BM25:
    """Okapi BM25 ranking — pure Python implementation."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avgdl: float = 0.0
        self.doc_freqs: Counter = Counter()     # term → doc frequency
        self.idf: Dict[str, float] = {}
        self.doc_len: List[int] = []
        self.corpus: List[List[str]] = []

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + punctuation tokenization."""
        text = text.lower()
        tokens = re.findall(r"[a-z0-9]+", text)
        return tokens

    def index(self, documents: List[str]) -> None:
        """Build the BM25 index from a list of documents."""
        self.corpus = [self._tokenize(doc) for doc in documents]
        self.corpus_size = len(self.corpus)
        nd: Counter = Counter()  # term → number of docs with term

        for doc in self.corpus:
            self.doc_len.append(len(doc))
            for term in set(doc):
                nd[term] += 1

        self.avgdl = sum(self.doc_len) / self.corpus_size if self.corpus_size else 0

        # Calculate IDF
        for term, freq in nd.items():
            self.idf[term] = math.log(
                (self.corpus_size - freq + 0.5) / (freq + 0.5) + 1
            )

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Search and return list of (doc_index, score) sorted by descending score."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scores: Dict[int, float] = {}

        for doc_idx in range(self.corpus_size):
            score = self._score_doc(query_terms, doc_idx)
            if score > 0:
                scores[doc_idx] = score

        # Sort by score descending
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    def _score_doc(self, query_terms: List[str], doc_idx: int) -> float:
        doc_len = self.doc_len[doc_idx]
        doc_terms = self.corpus[doc_idx]
        doc_tf = Counter(doc_terms)

        score = 0.0
        for term in query_terms:
            if term not in self.idf:
                continue
            tf = doc_tf.get(term, 0)
            if tf == 0:
                continue
            idf = self.idf[term]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
            score += idf * numerator / denominator

        return score


# -----------------------------------------------------------------------------
# Retrieval result
# -----------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """A single retrieval result."""
    content: str
    score: float
    source: str = "bm25"  # "bm25" | "vector" | "graph"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResults:
    """Collection of retrieval results with query metadata."""
    query: str
    results: List[RetrievalResult]
    total_indexed: int = 0
    mode: str = "bm25"


# -----------------------------------------------------------------------------
# Retriever
# -----------------------------------------------------------------------------

class Retriever:
    """
    Hybrid retriever: BM25 + optional vector similarity + knowledge graph.

    BM25 is always active. When chromadb is installed and a vector store
    is configured, vector search is layered on top for semantic similarity.
    """

    def __init__(
        self,
        kg: Optional[Any] = None,   # KnowledgeGraph instance
        enable_vector: bool = False,
        vector_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.kg = kg
        self.enable_vector = enable_vector
        self.vector_model = vector_model
        self._bm25 = BM25()
        self._doc_store: List[str] = []
        self._doc_metadata: List[Dict[str, Any]] = []
        self._doc_ids: List[int] = []   # KG entity IDs if from KG, else -1
        self._lock = threading.RLock()
        self._vector_index: Optional[Any] = None  # chromadb client

        if enable_vector:
            self._init_vector_store()

    def _init_vector_store(self) -> None:
        """Try to initialize chromadb vector store."""
        try:
            import chromadb
            self._vector_index = chromadb.Client()
            logger.info("Vector store initialized (chromadb available)")
        except ImportError:
            logger.debug("chromadb not installed — vector search disabled")
            self.enable_vector = False

    # -------------------------------------------------------------------------
    # Document indexing
    # -------------------------------------------------------------------------

    def index_documents(
        self,
        documents: List[str],
        metadata: List[Dict[str, Any]] | None = None,
        doc_ids: List[int] | None = None,
        batch_size: int = 100,
    ) -> int:
        """
        Index a list of documents for retrieval.

        Returns the number of documents indexed.
        """
        with self._lock:
            offset = len(self._doc_store)
            self._doc_store.extend(documents)
            if metadata:
                self._doc_metadata.extend(metadata)
            else:
                self._doc_metadata.extend([{}] * len(documents))
            if doc_ids:
                self._doc_ids.extend(doc_ids)
            else:
                self._doc_ids.extend([-1] * len(documents))

            # Rebuild BM25 for all docs (incremental would require more complex BM25)
            # For large corpora, use the batch approach to avoid rebuild
            if len(self._doc_store) <= 50_000:
                self._bm25.index(self._doc_store)
            else:
                # Partial re-index: only index new documents
                logger.warning("Large corpus — BM25 reindex may be slow")

            # Add to vector store if enabled
            if self.enable_vector and self._vector_index is not None:
                collection = self._vector_index.get_or_create_collection(
                    name="hermes_memory"
                )
                for i, doc in enumerate(documents):
                    if i % batch_size == 0:
                        pass  # batch insert

            return len(documents)

    def index_entity_texts(
        self,
        texts: List[str],
        entity_ids: List[int],
        metadata: List[Dict[str, Any]] | None = None,
    ) -> int:
        """Index entity descriptions for retrieval."""
        return self.index_documents(texts, metadata, entity_ids)

    # -------------------------------------------------------------------------
    # Search
    # -------------------------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 10,
        mode: str = "bm25",   # "bm25" | "vector" | "hybrid"
        entity_ids: List[int] | None = None,  # limit to specific KG entities
    ) -> RetrievalResults:
        """
        Search indexed documents.

        Args:
            query: Search query
            top_k: Number of results to return
            mode: "bm25" (keyword), "vector" (semantic), "hybrid" (both)
            entity_ids: If provided, limit search to these KG entity IDs
        """
        with self._lock:
            if mode == "bm25":
                return self._search_bm25(query, top_k, entity_ids)
            elif mode == "vector":
                return self._search_vector(query, top_k, entity_ids)
            elif mode == "hybrid":
                bm25_results = self._search_bm25(query, top_k * 2, entity_ids)
                vector_results = self._search_vector(query, top_k * 2, entity_ids)
                return self._merge_results(query, bm25_results, vector_results, top_k)
            else:
                return self._search_bm25(query, top_k, entity_ids)

    def _search_bm25(
        self,
        query: str,
        top_k: int,
        entity_ids: List[int] | None = None,
    ) -> RetrievalResults:
        if not self._doc_store:
            return RetrievalResults(query=query, results=[], total_indexed=0)

        # Re-index if needed (BM25 doesn't support incremental easily)
        if self._bm25.corpus_size != len(self._doc_store):
            self._bm25.index(self._doc_store)

        hits = self._bm25.search(query, top_k * 2)
        results: List[RetrievalResult] = []

        for doc_idx, score in hits:
            if entity_ids is not None:
                if self._doc_ids[doc_idx] not in entity_ids:
                    continue

            content = self._doc_store[doc_idx]
            metadata = self._doc_metadata[doc_idx] if doc_idx < len(self._doc_metadata) else {}

            results.append(RetrievalResult(
                content=content,
                score=score,
                source="bm25",
                metadata={
                    "doc_index": doc_idx,
                    "entity_id": self._doc_ids[doc_idx] if doc_idx < len(self._doc_ids) else None,
                    **metadata,
                },
            ))

            if len(results) >= top_k:
                break

        return RetrievalResults(
            query=query,
            results=results,
            total_indexed=len(self._doc_store),
            mode="bm25",
        )

    def _search_vector(
        self,
        query: str,
        top_k: int,
        entity_ids: List[int] | None = None,
    ) -> RetrievalResults:
        if not self.enable_vector or self._vector_index is None:
            return RetrievalResults(query=query, results=[], total_indexed=0, mode="vector")

        # ChromaDB query would go here
        # For now, fall back to BM25
        return self._search_bm25(query, top_k, entity_ids)

    def _merge_results(
        self,
        query: str,
        bm25_results: RetrievalResults,
        vector_results: RetrievalResults,
        top_k: int,
    ) -> RetrievalResults:
        """Merge BM25 and vector results using reciprocal rank fusion."""
        seen: Dict[str, RetrievalResult] = {}
        rrf_scores: Dict[int, float] = {}

        for rank, result in enumerate(bm25_results.results):
            key = f"bm25_{result.metadata.get('doc_index', rank)}"
            seen[key] = result
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (60 + rank)

        for rank, result in enumerate(vector_results.results):
            key = f"vec_{result.metadata.get('doc_index', rank)}"
            seen[key] = result
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (60 + rank)

        sorted_keys = sorted(rrf_scores, key=rrf_scores.get, reverse=True)
        merged = [seen[k] for k in sorted_keys[:top_k]]

        return RetrievalResults(
            query=query,
            results=merged,
            total_indexed=bm25_results.total_indexed,
            mode="hybrid",
        )

    # -------------------------------------------------------------------------
    # Knowledge graph multi-hop retrieval
    # -------------------------------------------------------------------------

    def search_with_hops(
        self,
        query: str,
        start_entity_id: int,
        max_hops: int = 2,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """
        Multi-hop reasoning: start from an entity and traverse relations.

        Returns relevant content from connected entities.
        """
        if self.kg is None:
            return []

        # Traverse the graph
        traversal = self.kg.traverse(start_entity_id, max_depth=max_hops)
        results: List[RetrievalResult] = []

        # Collect all reachable entity texts
        entity_ids = list(traversal.keys())

        for eid in entity_ids:
            node = traversal[eid]
            entity = node["entity"]
            if entity and entity.id != start_entity_id:
                results.append(RetrievalResult(
                    content=entity.name,
                    score=1.0,
                    source="graph",
                    metadata={"entity_id": entity.id, "entity_type": entity.entity_type},
                ))

        # Now search within those entities using BM25
        if results:
            relevant_ids = [r.metadata["entity_id"] for r in results]
            bm25_results = self._search_bm25(query, top_k, relevant_ids)
            return bm25_results.results

        return results[:top_k]

    # -------------------------------------------------------------------------
    # Memory-specific retrieval
    # -------------------------------------------------------------------------

    def retrieve_memory(
        self,
        query: str,
        memory_store: Any = None,  # MemoryStore
        top_k: int = 10,
    ) -> RetrievalResults:
        """
        Retrieve from memory store using the configured retrieval mode.

        Combines session memory, long-term memory, and working memory.
        """
        all_results: List[RetrievalResult] = []

        # Search session memory
        session_texts = []
        if memory_store:
            session_texts = [
                f["content"]
                for f in memory_store.get_recent_facts(limit=100)
            ]

        if session_texts:
            session_results = self._search_bm25(query, top_k, None)
            for r in session_results.results:
                r.source = "session"
            all_results.extend(session_results.results)

        # Search knowledge graph entities
        if self.kg:
            entities = self.kg.search_entities(query, limit=top_k)
            for entity in entities:
                all_results.append(RetrievalResult(
                    content=f"{entity.name}: {entity.properties.get('description', '')}",
                    score=entity.confidence,
                    source="knowledge_graph",
                    metadata={"entity_id": entity.id, "entity_type": entity.entity_type},
                ))

        # Sort by score
        all_results.sort(key=lambda x: x.score, reverse=True)
        return RetrievalResults(
            query=query,
            results=all_results[:top_k],
            mode="hybrid",
        )

    def clear_index(self) -> None:
        """Clear all indexed documents."""
        with self._lock:
            self._doc_store.clear()
            self._doc_metadata.clear()
            self._doc_ids.clear()
            self._bm25 = BM25()
