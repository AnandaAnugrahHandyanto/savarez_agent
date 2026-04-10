#!/usr/bin/env python3
"""
HermesMemory Dual-Retriever: BM25 + Semantic Late Fusion

MemPalace uses only ChromaDB semantic search. HermesMemory fuses:
1. BM25 (keyword/bm25) - exact match, robust to vocabulary gaps
2. Semantic (ChromaDB/bge) - meaning-based retrieval
3. Late fusion: combine scores with learned/optimized weights

This approach captures both exact keyword matches (BM25's strength)
and semantic similarity (ChromaDB's strength), with late fusion being
superior to early fusion because each retriever maintains its natural ranking.
"""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Optional

import chromadb


# =============================================================================
# BM25 SCORER (from scratch - no rank_bm25 dependency needed)
# =============================================================================


class BM25:
    """
    BM25 scorer - O(1) per-document scoring with precomputed term stats.
    
    MemPalace's hybrid mode uses simple keyword overlap which is a weak proxy
    for true BM25. BM25 accounts for:
    - Term frequency saturation (diminishing returns)
    - Document length normalization
    - Inverse document frequency (rare terms weighted higher)
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.term_doc_freqs: dict[str, int] = {}
        self.avgdl: float = 0
        self.N: int = 0
        self.doc_lengths: list[int] = []
        self.doc_term_freqs: list[dict[str, int]] = []

    def fit(self, documents: list[str]):
        """Precompute statistics for all documents."""
        self.N = len(documents)
        self.term_doc_freqs = defaultdict(int)
        self.doc_lengths = []
        self.doc_term_freqs = []

        total_len = 0
        for doc in documents:
            tokens = self._tokenize(doc)
            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)

            for term in tf:
                self.term_doc_freqs[term] += 1

        self.avgdl = total_len / max(self.N, 1)

    def score(self, query: str, doc_idx: int) -> float:
        """BM25 score for a single document."""
        tokens = self._tokenize(query)
        doc_tf = self.doc_term_freqs[doc_idx]
        doc_len = self.doc_lengths[doc_idx]

        score = 0.0
        for term in tokens:
            if term in doc_tf:
                tf = doc_tf[term]
                df = self.term_doc_freqs[term]
                idf = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                score += idf * numerator / denominator
        return score

    def score_batch(self, query: str) -> list[float]:
        """BM25 scores for all documents."""
        tokens = self._tokenize(query)
        scores = []
        for doc_idx in range(self.N):
            score = self.score(query, doc_idx)  # reuse tokenized query
            scores.append(score)
        return scores

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple tokenization: lowercase, alphanumeric tokens >= 3 chars."""
        return re.findall(r'\b[a-z0-9]{3,}\b', text.lower())


# =============================================================================
# STOP WORDS
# =============================================================================

STOP_WORDS = {
    'what', 'when', 'where', 'who', 'how', 'which', 'did', 'do', 'was', 'were',
    'have', 'has', 'had', 'is', 'are', 'the', 'a', 'an', 'my', 'me', 'i',
    'you', 'your', 'their', 'it', 'its', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'ago', 'last', 'that', 'this', 'there',
    'about', 'get', 'got', 'give', 'gave', 'buy', 'bought', 'made', 'make',
    'be', 'being', 'been', 'am', 'being', 'being'
}


# =============================================================================
# QUERY PROCESSING
# =============================================================================


def extract_keywords(text: str) -> list[str]:
    """Extract non-stopword keywords from text."""
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def keyword_overlap(query: str, document: str) -> float:
    """Fraction of query keywords present in document."""
    query_kws = set(extract_keywords(query))
    if not query_kws:
        return 0.0
    doc_lower = document.lower()
    hits = sum(1 for kw in query_kws if kw in doc_lower)
    return hits / len(query_kws)


# =============================================================================
# FUSION STRATEGIES
# =============================================================================


def late_fusion_rrf(scores_list: list[list[float]], k: int = 60) -> list[float]:
    """
    Reciprocal Rank Fusion - combine rankings from multiple retrievers.
    
    MemPalace uses linear fusion: fused = sem * (1 + kw_weight * overlap)
    RRF is more robust because it operates on ranks, not raw scores.
    
    RRF formula: sum(1 / (k + rank_i)) for each retriever i
    """
    fused = [0.0] * len(scores_list[0])
    for scores in scores_list:
        # Get ranks (higher score = better rank = lower rank number)
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        for rank, (doc_idx, _) in enumerate(indexed_scores, 1):
            fused[doc_idx] += 1.0 / (k + rank)
    return fused


def late_fusion_linear(weights: list[float], scores_list: list[list[float]]) -> list[float]:
    """Weighted linear fusion of scores."""
    fused = [0.0] * len(scores_list[0])
    for weight, scores in zip(weights, scores_list):
        for i, score in enumerate(scores):
            fused[i] += weight * score
    return fused


def normalize_scores(scores: list[float]) -> list[float]:
    """Min-max normalize scores to [0, 1]."""
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [0.5] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class RetrievalResult:
    doc_idx: int
    corpus_id: str
    text: str
    fused_score: float
    semantic_score: float
    bm25_score: float
    keyword_overlap: float


# =============================================================================
# DUAL RETRIEVER
# =============================================================================


class DualRetriever:
    """
    HermesMemory's core: BM25 + Semantic Late Fusion retriever.
    
    Improvements over MemPalace:
    1. True BM25 instead of keyword overlap
    2. Separate term frequency saturation
    3. Late fusion (RRF) instead of linear fusion
    4. Keyword overlap as separate feature, not fusion modifier
    """

    def __init__(
        self,
        embed_fn=None,  # ChromaDB embedding function
        bm25_weight: float = 0.4,
        sem_weight: float = 0.4,
        kw_weight: float = 0.2,
        use_rrf: bool = True,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.embed_fn = embed_fn
        self.bm25_weight = bm25_weight
        self.sem_weight = sem_weight
        self.kw_weight = kw_weight
        self.use_rrf = use_rrf
        self.bm25 = BM25(k1=k1, b=b)
        self._chroma_client = None
        self._collection = None
        self.corpus: list[str] = []
        self.corpus_ids: list[str] = []
        self.corpus_timestamps: list[str] = []
        self._doc_idx_to_corpus_idx: dict[int, int] = {}

    def index(self, corpus: list[str], corpus_ids: list[str], timestamps: list[str]):
        """Build BM25 index and ChromaDB collection."""
        self.corpus = corpus
        self.corpus_ids = corpus_ids
        self.corpus_timestamps = timestamps

        # Build BM25 index
        self.bm25.fit(corpus)

        # Build ChromaDB collection
        self._chroma_client = chromadb.EphemeralClient()
        self._collection = self._chroma_client.create_collection(
            "hermes_drawers",
            embedding_function=self.embed_fn
        )
        self._collection.add(
            documents=corpus,
            ids=[f"doc_{i}" for i in range(len(corpus))],
            metadatas=[
                {"corpus_id": cid, "timestamp": ts}
                for cid, ts in zip(corpus_ids, timestamps)
            ],
        )

    def retrieve(
        self, query: str, top_k: int = 50
    ) -> list[RetrievalResult]:
        """
        Retrieve documents using BM25 + semantic late fusion.
        
        Returns top-k results sorted by fused score.
        """
        if not self.corpus:
            return []

        n = len(self.corpus)

        # 1. BM25 scores
        bm25_scores = self.bm25.score_batch(query)

        # 2. Semantic scores via ChromaDB
        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k * 2, n),  # retrieve extra for robustness
            include=["distances", "metadatas"],
        )
        chroma_ids = results["ids"][0]
        chroma_dists = results["distances"][0]
        
        # Convert ChromaDB distances to similarity scores
        # ChromaDB returns L2 distance; convert to similarity
        sem_scores = [0.0] * n
        for rid, dist in zip(chroma_ids, chroma_dists):
            doc_idx = int(rid.split("_")[1])
            sem_scores[doc_idx] = 1.0 - dist  # convert distance to similarity

        # 3. Keyword overlap
        kw_scores = [
            keyword_overlap(query, doc) for doc in self.corpus
        ]

        # 4. Late fusion
        if self.use_rrf:
            # Normalize each score type to [0, 1] before RRF
            fused = late_fusion_rrf([
                normalize_scores(bm25_scores),
                normalize_scores(sem_scores),
                normalize_scores(kw_scores),
            ])
        else:
            # Linear fusion with weights
            fused = late_fusion_linear(
                [self.bm25_weight, self.sem_weight, self.kw_weight],
                [bm25_scores, sem_scores, kw_scores]
            )

        # 5. Rank by fused score
        indexed = list(enumerate(fused))
        indexed.sort(key=lambda x: x[1], reverse=True)

        results_out = []
        for rank, (doc_idx, score) in enumerate(indexed[:top_k], 1):
            results_out.append(RetrievalResult(
                doc_idx=doc_idx,
                corpus_id=self.corpus_ids[doc_idx],
                text=self.corpus[doc_idx],
                fused_score=score,
                semantic_score=sem_scores[doc_idx],
                bm25_score=bm25_scores[doc_idx],
                keyword_overlap=kw_scores[doc_idx],
            ))

        return results_out


# =============================================================================
# TEMPORAL BOOST (enhanced from MemPalace)
# =============================================================================


def parse_relative_date(text: str) -> Optional[tuple[int, int]]:
    """
    Parse relative time references.
    Returns (days_ago, tolerance) or None.
    """
    text = text.lower()
    patterns = [
        (r'(\d+)\s+days?\s+ago', lambda m: (int(m.group(1)), 2)),
        (r'a\s+couple\s+(?:of\s+)?days?\s+ago', lambda m: (2, 2)),
        (r'yesterday', lambda m: (1, 1)),
        (r'a\s+week\s+ago', lambda m: (7, 3)),
        (r'(\d+)\s+weeks?\s+ago', lambda m: (int(m.group(1)) * 7, 5)),
        (r'last\s+week', lambda m: (7, 3)),
        (r'a\s+month\s+ago', lambda m: (30, 7)),
        (r'(\d+)\s+months?\s+ago', lambda m: (int(m.group(1)) * 30, 10)),
        (r'last\s+month', lambda m: (30, 7)),
        (r'last\s+year', lambda m: (365, 30)),
        (r'a\s+year\s+ago', lambda m: (365, 30)),
        (r'recently', lambda m: (14, 14)),
    ]
    import re as _re
    for pattern, extractor in patterns:
        m = _re.search(pattern, text)
        if m:
            return extractor(m)
    return None


def apply_temporal_boost(
    results: list[RetrievalResult],
    query_date: str,
    haystack_dates: dict[str, str],  # corpus_id -> date string
    boost_strength: float = 0.3,
) -> list[RetrievalResult]:
    """
    Apply temporal proximity boost to results.
    
    Enhanced from MemPalace: uses date string parsing instead of just proximity.
    """
    from datetime import datetime
    
    try:
        q_date = datetime.strptime(query_date.split(" (")[0], "%Y/%m/%d")
    except (ValueError, AttributeError):
        return results
    
    boosted = []
    for r in results:
        date_str = haystack_dates.get(r.corpus_id, "")
        try:
            d = datetime.strptime(date_str.split(" (")[0], "%Y/%m/%d")
            days_diff = abs((q_date - d).days)
            # Gaussian-like decay: max boost at 0 days, ~0 at 30 days
            temporal_score = math.exp(-(days_diff ** 2) / (2 * 15 ** 2))
            boost = boost_strength * temporal_score
            new_fused = r.fused_score * (1 + boost)
        except (ValueError, AttributeError):
            new_fused = r.fused_score
        
        boosted.append(RetrievalResult(
            doc_idx=r.doc_idx,
            corpus_id=r.corpus_id,
            text=r.text,
            fused_score=new_fused,
            semantic_score=r.semantic_score,
            bm25_score=r.bm25_score,
            keyword_overlap=r.keyword_overlap,
        ))
    
    boosted.sort(key=lambda x: x.fused_score, reverse=True)
    return boosted
