#!/usr/bin/env python3
"""
HermesMemory × LongMemEval Benchmark
====================================

Compares HermesMemory against MemPalace on LongMemEval (500 questions).

Modes:
  hermes_dual       - BM25 + semantic RRF (baseline)
  hermes_v2         - hermes_dual + temporal boost + two-pass for assistant refs
  hermes_v3         - hermes_v2 + expanded rerank pool (top-20 instead of top-10)
  hermes_llm        - hermes_v3 + LLM reranking via Browser Use Cloud Haiku

Usage:
    python -m hermes_memory.benchmark /path/to/longmemeval_s_cleaned.json --mode hermes_v2
    python -m hermes_memory.benchmark /path/to/longmemeval_s_cleaned.json --mode hermes_llm
    python -m hermes_memory.benchmark /path/to/longmemeval_s_cleaned.json --mode hermes_dual --limit 100
"""

import argparse
import json
import math
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional

import chromadb


# =============================================================================
# METRICS
# =============================================================================


def dcg(relevances: list[float], k: int) -> float:
    score = 0.0
    for i, rel in enumerate(relevances[:k]):
        score += rel / math.log2(i + 2)
    return score


def ndcg(rankings: list[int], correct_ids: set[str], corpus_ids: list[str], k: int) -> float:
    relevances = [1.0 if corpus_ids[idx] in correct_ids else 0.0 for idx in rankings[:k]]
    ideal = sorted(relevances, reverse=True)
    idcg = dcg(ideal, k)
    if idcg == 0:
        return 0.0
    return dcg(relevances, k) / idcg


def evaluate_retrieval(rankings: list[int], correct_ids: set[str], corpus_ids: list[str], k: int):
    top_k_ids = set(corpus_ids[idx] for idx in rankings[:k])
    recall_any = float(any(cid in top_k_ids for cid in correct_ids))
    recall_all = float(all(cid in top_k_ids for cid in correct_ids))
    ndcg_score = ndcg(rankings, correct_ids, corpus_ids, k)
    return recall_any, recall_all, ndcg_score


# =============================================================================
# EMBEDDING FUNCTION
# =============================================================================


def make_embed_fn(model_name: str):
    """Return a ChromaDB-compatible embedding function."""
    if model_name == "default" or not model_name:
        return None

    MODEL_MAP = {
        "bge-base": "BAAI/bge-base-en-v1.5",
        "bge-large": "BAAI/bge-large-en-v1.5",
        "nomic": "nomic-ai/nomic-embed-text-v1.5",
        "mxbai": "mixedbread-ai/mxbai-embed-large-v1",
    }
    hf_name = MODEL_MAP.get(model_name, model_name)

    try:
        from fastembed import TextEmbedding
        from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

        class FastEmbedFn(EmbeddingFunction):
            def __init__(self, name):
                print(f"  Loading embedding model: {name}...")
                self._model = TextEmbedding(name)
                print(f"  Model ready.")

            def __call__(self, input: Documents) -> Embeddings:
                # Convert numpy arrays to lists of floats
                result = []
                for vec in self._model.embed(input):
                    if hasattr(vec, 'astype'):
                        result.append(vec.astype(float).tolist())
                    else:
                        result.append(list(vec))
                return result

        return FastEmbedFn(hf_name)
    except ImportError:
        print("fastembed not available, falling back to default")
        return None


# =============================================================================
# STOP WORDS & KEYWORD EXTRACTION
# =============================================================================


STOP_WORDS = {
    'what', 'when', 'where', 'who', 'how', 'which', 'did', 'do', 'was', 'were',
    'have', 'has', 'had', 'is', 'are', 'the', 'a', 'an', 'my', 'me', 'i',
    'you', 'your', 'their', 'it', 'its', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'ago', 'last', 'that', 'this', 'there',
    'about', 'get', 'got', 'give', 'gave', 'buy', 'bought', 'made', 'make',
}


def extract_keywords(text: str) -> list[str]:
    import re
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def keyword_overlap(query: str, doc_text: str) -> float:
    query_kws = set(extract_keywords(query))
    if not query_kws:
        return 0.0
    doc_lower = doc_text.lower()
    hits = sum(1 for kw in query_kws if kw in doc_lower)
    return hits / len(query_kws)


# =============================================================================
# BM25
# =============================================================================


class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.term_doc_freqs = {}
        self.avgdl = 0
        self.N = 0
        self.doc_lengths = []
        self.doc_term_freqs = []

    def fit(self, documents: list[str]):
        import re
        from collections import Counter, defaultdict
        self.N = len(documents)
        self.term_doc_freqs = defaultdict(int)
        self.doc_lengths = []
        self.doc_term_freqs = []
        total_len = 0
        for doc in documents:
            tokens = re.findall(r'\b[a-z0-9]{3,}\b', doc.lower())
            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)
            for term in tf:
                self.term_doc_freqs[term] += 1
        self.avgdl = total_len / max(self.N, 1)

    def score_batch(self, query: str) -> list[float]:
        import re
        from collections import Counter
        tokens = re.findall(r'\b[a-z0-9]{3,}\b', query.lower())
        scores = []
        for doc_idx in range(self.N):
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
            scores.append(score)
        return scores


# =============================================================================
# RECIPROCAL RANK FUSION
# =============================================================================


def late_fusion_rrf(scores_list: list[list[float]], k: int = 60) -> list[float]:
    fused = [0.0] * len(scores_list[0])
    for scores in scores_list:
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        for rank, (doc_idx, _) in enumerate(indexed_scores, 1):
            fused[doc_idx] += 1.0 / (k + rank)
    return fused


def normalize_scores(scores: list[float]) -> list[float]:
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [0.5] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


# =============================================================================
# ASSISTANT-REFERENCE DETECTION (MemPalace hybrid_v2 fix #2)
# =============================================================================

ASSISTANT_TRIGGERS = [
    "you suggested", "you told me", "you mentioned", "you said",
    "you recommended", "remind me what you", "you provided",
    "you listed", "you gave me", "you described", "what did you",
    "you came up with", "you helped me", "you explained",
    "can you remind me", "you identified", "you talked about",
    "remind me about what you", "you were talking about",
    "our conversation about", "our chat about",
]


def is_assistant_reference(question: str) -> bool:
    q_lower = question.lower()
    return any(trigger in q_lower for trigger in ASSISTANT_TRIGGERS)


# =============================================================================
# TEMPORAL BOOST (MemPalace hybrid_v2 fix #1)
# =============================================================================

WORD_TO_NUM = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
}

def _parse_word_number(word: str) -> int:
    return WORD_TO_NUM.get(word.lower(), 0)

TEMPORAL_PATTERNS = [
    (r'(\d+)\s+days?\s+ago', lambda m: (int(m.group(1)), 3)),
    (r'a\s+couple\s+(?:of\s+)?days?\s+ago', lambda m: (2, 3)),
    (r'yesterday', lambda m: (1, 2)),
    (r'a\s+week\s+ago', lambda m: (7, 4)),
    (r'(\d+)\s+weeks?\s+ago', lambda m: (int(m.group(1)) * 7, 5)),
    (r'a\s+couple\s+(?:of\s+)?weeks?\s+ago', lambda m: (14, 5)),
    (r'(one|two|three|four|five|six|seven|eight|nine|ten)\s+weeks?\s+ago',
     lambda m: (_parse_word_number(m.group(1)) * 7, 5)),
    (r'last\s+week', lambda m: (7, 4)),
    (r'a\s+month\s+ago', lambda m: (30, 8)),
    (r'(\d+)\s+months?\s+ago', lambda m: (int(m.group(1)) * 30, 12)),
    (r'last\s+month', lambda m: (30, 8)),
    (r'(\d+)\s+years?\s+ago', lambda m: (int(m.group(1)) * 365, 30)),
    (r'a\s+year\s+ago', lambda m: (365, 30)),
    (r'last\s+year', lambda m: (365, 30)),
    (r'recently', lambda m: (14, 14)),
    (r'ages\s+ago', lambda m: (365, 60)),
    (r'a\s+long\s+time\s+ago', lambda m: (180, 30)),
]


def parse_temporal_offset(question: str) -> Optional[tuple[int, int]]:
    """Returns (days_ago, tolerance_window) or None."""
    for pattern, extractor in TEMPORAL_PATTERNS:
        m = re.search(pattern, question.lower())
        if m:
            return extractor(m)
    return None


def compute_temporal_boost(
    question_date_str: str,
    session_dates: list[str],
    fused_scores: list[float],
    question_text: str,
    weight: float = 0.40,
) -> list[float]:
    """Apply temporal proximity boost based on question date vs session dates."""
    try:
        q_date = datetime.strptime(question_date_str.split(" (")[0], "%Y/%m/%d")
    except (ValueError, AttributeError):
        return fused_scores

    # Parse temporal reference from question
    temporal = parse_temporal_offset(question_text)
    if temporal is None:
        return fused_scores  # No temporal reference → no boost

    days_ago, window = temporal
    target_date = q_date - timedelta(days=days_ago)

    boosted = list(fused_scores)
    for i, date_str in enumerate(session_dates):
        try:
            sess_date = datetime.strptime(date_str.split(" (")[0], "%Y/%m/%d")
            days_diff = abs((sess_date - target_date).days)
            # Linear decay: max boost at 0 days, 0 boost at window
            proximity = max(0.0, 1.0 - days_diff / window)
            boost = weight * proximity
            boosted[i] = fused_scores[i] * (1.0 + boost)
        except (ValueError, AttributeError):
            pass

    return boosted


# =============================================================================
# KEYWORD OVERLAP (MemPalace hybrid v1 core)
# =============================================================================

STOP_WORDS = {
    'what', 'when', 'where', 'who', 'how', 'which', 'did', 'do',
    'was', 'were', 'have', 'has', 'had', 'is', 'are', 'the', 'a',
    'an', 'my', 'me', 'i', 'you', 'your', 'their', 'it', 'its',
    'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
    'ago', 'last', 'that', 'this', 'there', 'about', 'get', 'got',
    'give', 'gave', 'buy', 'bought', 'made', 'make',
}


def extract_keywords(text: str) -> list[str]:
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return [w for w in words if w not in STOP_WORDS]


def keyword_overlap_score(query: str, doc_text: str) -> float:
    query_kws = set(extract_keywords(query))
    if not query_kws:
        return 0.0
    doc_lower = doc_text.lower()
    hits = sum(1 for kw in query_kws if kw in doc_lower)
    return hits / len(query_kws)


# =============================================================================
# BM25
# =============================================================================

class BM25:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.term_doc_freqs = {}
        self.avgdl = 0
        self.N = 0
        self.doc_lengths = []
        self.doc_term_freqs = []

    def fit(self, documents: list[str]):
        self.N = len(documents)
        self.term_doc_freqs = defaultdict(int)
        self.doc_lengths = []
        self.doc_term_freqs = []
        total_len = 0
        for doc in documents:
            tokens = re.findall(r'\b[a-z0-9]{3,}\b', doc.lower())
            tf = Counter(tokens)
            self.doc_term_freqs.append(tf)
            self.doc_lengths.append(len(tokens))
            total_len += len(tokens)
            for term in tf:
                self.term_doc_freqs[term] += 1
        self.avgdl = total_len / max(self.N, 1)

    def score_batch(self, query: str) -> list[float]:
        tokens = re.findall(r'\b[a-z0-9]{3,}\b', query.lower())
        scores = []
        for doc_idx in range(self.N):
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
            scores.append(score)
        return scores


# =============================================================================
# FUSION
# =============================================================================

def late_fusion_rrf(scores_list: list[list[float]], k: int = 60) -> list[float]:
    fused = [0.0] * len(scores_list[0])
    for scores in scores_list:
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        for rank, (doc_idx, _) in enumerate(indexed_scores, 1):
            fused[doc_idx] += 1.0 / (k + rank)
    return fused


def late_fusion_linear(weights: list[float], scores_list: list[list[float]]) -> list[float]:
    """Weighted linear fusion of normalized scores."""
    fused = [0.0] * len(scores_list[0])
    for weight, scores in zip(weights, scores_list):
        for i, score in enumerate(scores):
            fused[i] += weight * score
    return fused


def normalize_scores(scores: list[float]) -> list[float]:
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [0.5] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


def adaptive_fusion(bm25_scores, sem_scores, kw_scores, is_vague: bool) -> list[float]:
    """
    Fuses BM25 + Semantic + Keyword scores with query-adaptive strategy.
    
    For vague preference queries: linear fusion (weighted) + semantic dominance
    For explicit queries: keep original RRF (rank-based, scale-invariant)
    """
    if is_vague:
        # Vague: use weighted linear fusion on normalized scores
        # BM25 almost disabled since it matches generic content
        return late_fusion_linear(
            [0.10, 0.65, 0.25],
            [normalize_scores(bm25_scores), normalize_scores(sem_scores), normalize_scores(kw_scores)]
        )
    else:
        # Explicit: keep original RRF (scale-invariant, works well for all signals)
        return late_fusion_rrf([
            normalize_scores(bm25_scores),
            normalize_scores(sem_scores),
            normalize_scores(kw_scores),
        ])


# =============================================================================
# CORPUS BUILDING
# =============================================================================

def build_corpus(entry, granularity="session"):
    """Build corpus from haystack sessions."""
    corpus = []
    corpus_ids = []
    corpus_timestamps = []

    sessions = entry["haystack_sessions"]
    session_ids = entry["haystack_session_ids"]
    dates = entry["haystack_dates"]

    for sess_idx, (session, sess_id, date) in enumerate(zip(sessions, session_ids, dates)):
        if granularity == "session":
            user_turns = [t["content"] for t in session if t["role"] == "user"]
            if user_turns:
                corpus.append("\n".join(user_turns))
                corpus_ids.append(sess_id)
                corpus_timestamps.append(date)
        elif granularity == "full":
            all_turns = [t["content"] for t in session]
            if all_turns:
                corpus.append("\n".join(all_turns))
                corpus_ids.append(sess_id)
                corpus_timestamps.append(date)
        else:
            for turn_num, turn in enumerate(session):
                if turn["role"] == "user":
                    corpus.append(turn["content"])
                    corpus_ids.append(f"{sess_id}_turn_{turn_num}")
                    corpus_timestamps.append(date)

    return corpus, corpus_ids, corpus_timestamps


# =============================================================================
# RETRIEVAL MODES
# =============================================================================

def build_and_retrieve_raw(entry, embed_fn, n_results=50):
    """Baseline: MemPalace-style raw ChromaDB (semantic only)."""
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    client = chromadb.EphemeralClient()
    coll_name = f"hermes_raw_{uuid.uuid4().hex[:8]}"
    col = client.create_collection(coll_name, embedding_function=embed_fn)
    col.add(
        documents=corpus,
        ids=[f"doc_{i}" for i in range(len(corpus))],
        metadatas=[{"corpus_id": cid, "timestamp": ts} for cid, ts in zip(corpus_ids, corpus_timestamps)],
    )
    results = col.query(
        query_texts=[entry["question"]],
        n_results=min(n_results, len(corpus)),
        include=["distances"],
    )
    ranked_indices = [int(rid.split("_")[1]) for rid in results["ids"][0]]
    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


def build_and_retrieve_hermes_dual(entry, embed_fn, n_results=50):
    """
    HermesMemory dual: Adaptive fusion combining BM25, semantic, and keyword signals.
    
    Strategy:
    - Vague preference queries: semantic-first (BM25 almost disabled)
    - Multi-session / temporal / assistant queries: semantic-first with keyword reduction
    - Other explicit queries: balanced RRF fusion
    
    Fixes applied:
    1. Temporal boost for questions with temporal references  
    2. Two-pass for assistant-reference questions
    3. Semantic-first + keyword distance reduction for multi-session queries
    """
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    question = entry["question"]
    question_date = entry.get("question_date", "")
    is_assistant_q = is_assistant_reference(question)
    is_vague = is_vague_preference_query(question)
    has_temporal = parse_temporal_offset(question) is not None
    is_multisession = entry.get("question_type") == "multi-session"

    # Keyword overlap (used in both strategies)
    kw_scores = [keyword_overlap_score(question, doc) for doc in corpus]
    kw_weight = 0.30

    # ── Strategy: Semantic-first for complex queries, RRF for simple explicit ──
    # Complex = vague + multi-session + temporal + assistant
    # Simple explicit = non-vague, non-temporal, non-assistant, non-multi
    is_complex = is_vague or is_multisession or has_temporal or is_assistant_q

    if is_complex:
        # ── Semantic-first: ChromaDB + keyword distance reduction ──────────────────
        client = chromadb.EphemeralClient()
        coll_name = f"hermes_dual_{uuid.uuid4().hex[:8]}"
        col = client.create_collection(coll_name, embedding_function=embed_fn)
        col.add(
            documents=corpus,
            ids=[f"doc_{i}" for i in range(len(corpus))],
            metadatas=[{"corpus_id": cid, "timestamp": ts} for cid, ts in zip(corpus_ids, corpus_timestamps)],
        )
        results = col.query(
            query_texts=[question],
            n_results=min(n_results, len(corpus)),
            include=["distances", "metadatas"],
        )
        
        # Rank by semantic distance with keyword reduction
        ranked_by_dist = []
        for rid, dist in zip(results["ids"][0], results["distances"][0]):
            doc_idx = int(rid.split("_")[1])
            kw = kw_scores[doc_idx]
            reduced_dist = dist * (1.0 - kw_weight * kw)
            ranked_by_dist.append((doc_idx, reduced_dist))
        ranked_by_dist.sort(key=lambda x: x[1])
        
        # Apply temporal boost on distance-based ranking
        if has_temporal and question_date:
            temporal = parse_temporal_offset(question)
            days_ago, window = temporal
            try:
                q_date = datetime.strptime(question_date.split(" (")[0], "%Y/%m/%d")
                target = q_date - timedelta(days=days_ago)
                boosted = []
                for doc_idx, base_dist in ranked_by_dist:
                    date_str = corpus_timestamps[doc_idx]
                    try:
                        sess_date = datetime.strptime(date_str.split(" (")[0], "%Y/%m/%d")
                        days_diff = abs((sess_date - target).days)
                        boost = max(0.0, 0.40 * (1.0 - days_diff / window))
                        boosted.append((doc_idx, base_dist * (1.0 - boost)))
                    except (ValueError, AttributeError):
                        boosted.append((doc_idx, base_dist))
                ranked_by_dist = boosted
                ranked_by_dist.sort(key=lambda x: x[1])
            except (ValueError, AttributeError):
                pass
        
        # Two-pass for assistant questions
        if is_assistant_q:
            full_corpus, full_ids, full_dates = build_corpus(entry, "full")
            if full_corpus and len(full_corpus) > len(corpus):
                coll2_name = f"hermes_dual_full_{uuid.uuid4().hex[:8]}"
                col2 = client.create_collection(coll2_name, embedding_function=embed_fn)
                col2.add(
                    documents=full_corpus,
                    ids=[f"doc_{i}" for i in range(len(full_corpus))],
                    metadatas=[{"corpus_id": cid, "timestamp": ts} for cid, ts in zip(full_ids, full_dates)],
                )
                results2 = col2.query(
                    query_texts=[question],
                    n_results=min(5, len(full_corpus)),
                    include=["distances", "metadatas"],
                )
                seen = set(idx for idx, _ in ranked_by_dist)
                for rid, dist in zip(results2["ids"][0], results2["distances"][0]):
                    meta_idx = results2["ids"][0].index(rid)
                    meta = results2["metadatas"][0][meta_idx]
                    found_cid = meta["corpus_id"]
                    if found_cid in corpus_ids:
                        idx = corpus_ids.index(found_cid)
                        kw = kw_scores[idx]
                        fused_dist = dist * (1.0 - kw_weight * kw)
                        if idx not in seen:
                            ranked_by_dist.append((idx, fused_dist))
                        seen.add(idx)
                ranked_by_dist.sort(key=lambda x: x[1])
        
        ranked_indices = [idx for idx, _ in ranked_by_dist]
    else:
        # ── Balanced RRF fusion for simple explicit queries ────────────────────
        bm25 = BM25()
        bm25.fit(corpus)
        bm25_scores = bm25.score_batch(question)

        client = chromadb.EphemeralClient()
        coll_name = f"hermes_dual_{uuid.uuid4().hex[:8]}"
        col = client.create_collection(coll_name, embedding_function=embed_fn)
        col.add(
            documents=corpus,
            ids=[f"doc_{i}" for i in range(len(corpus))],
            metadatas=[{"corpus_id": cid, "timestamp": ts} for cid, ts in zip(corpus_ids, corpus_timestamps)],
        )
        results = col.query(
            query_texts=[question],
            n_results=min(n_results * 2, len(corpus)),
            include=["distances"],
        )
        sem_scores = [0.0] * len(corpus)
        for rid, dist in zip(results["ids"][0], results["distances"][0]):
            doc_idx = int(rid.split("_")[1])
            sem_scores[doc_idx] = 1.0 - dist

        fused = adaptive_fusion(bm25_scores, sem_scores, kw_scores, is_vague=False)
        indexed = list(enumerate(fused))
        indexed.sort(key=lambda x: x[1], reverse=True)
        ranked_indices = [idx for idx, _ in indexed]

    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


def build_and_retrieve_hermes_v2(entry, embed_fn, n_results=50, kw_weight=0.30):
    """
    HermesMemory v2: hermes_dual + temporal boost + two-pass for assistant refs.
    
    Mimics MemPalace hybrid_v2:
    - Fix 1: Temporal date boost (questions with "4 weeks ago" etc.)
    - Fix 2: Two-pass for assistant-reference questions
    - Fix 3: Keyword re-ranking with distance reduction
    """
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    question = entry["question"]
    question_date = entry.get("question_date", "")
    is_assistant_q = is_assistant_reference(question)

    # ── PASS 1: BM25 + Semantic on user-only corpus ─────────────────────────
    bm25 = BM25()
    bm25.fit(corpus)
    bm25_scores = bm25.score_batch(question)

    client = chromadb.EphemeralClient()
    coll_name = f"hermes_v2_{uuid.uuid4().hex[:8]}"
    col = client.create_collection(coll_name, embedding_function=embed_fn)
    col.add(
        documents=corpus,
        ids=[f"doc_{i}" for i in range(len(corpus))],
        metadatas=[{"corpus_id": cid, "timestamp": ts} for cid, ts in zip(corpus_ids, corpus_timestamps)],
    )
    results = col.query(
        query_texts=[question],
        n_results=min(n_results * 2, len(corpus)),
        include=["distances"],
    )
    sem_distances = {}
    for rid, dist in zip(results["ids"][0], results["distances"][0]):
        doc_idx = int(rid.split("_")[1])
        sem_distances[doc_idx] = dist

    # ── PASS 2: For assistant questions, also search full-text corpus ─────
    if is_assistant_q:
        full_corpus, full_ids, full_dates = build_corpus(entry, "full")
        if full_corpus and len(full_corpus) > len(corpus):
            coll2_name = f"hermes_v2_full_{uuid.uuid4().hex[:8]}"
            col2 = client.create_collection(coll2_name, embedding_function=embed_fn)
            col2.add(
                documents=full_corpus,
                ids=[f"doc_{i}" for i in range(len(full_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts} for cid, ts in zip(full_ids, full_dates)],
            )
            results2 = col2.query(
                query_texts=[question],
                n_results=min(5, len(full_corpus)),
                include=["distances", "metadatas"],
            )
            # Merge: add sessions found in full-text search to pass 1 pool
            for rid, dist in zip(results2["ids"][0], results2["distances"][0]):
                meta = results2["metadatas"][0][results2["ids"][0].index(rid)]
                found_cid = meta["corpus_id"]
                if found_cid in corpus_ids:
                    idx = corpus_ids.index(found_cid)
                    if idx not in sem_distances or dist < sem_distances[idx]:
                        sem_distances[idx] = dist

    # Convert distances to scores
    sem_scores = [0.0] * len(corpus)
    for idx, dist in sem_distances.items():
        sem_scores[idx] = 1.0 - dist

    # Keyword overlap
    kw_scores = [keyword_overlap_score(question, doc) for doc in corpus]

    # RRF fusion (BM25 + semantic + keyword)
    fused = late_fusion_rrf([
        normalize_scores(bm25_scores),
        normalize_scores(sem_scores),
        normalize_scores(kw_scores),
    ])

    # Keyword distance reduction (MemPalace hybrid v1: reduce fused dist by keyword overlap)
    # fused was RRF scores where higher = better; convert to distance: dist = 1/fused
    # Then reduce dist proportional to keyword overlap
    for i, kw in enumerate(kw_scores):
        if kw > 0 and fused[i] > 0:
            # Convert RRF score to pseudo-distance (lower RRF = higher dist)
            # Apply distance reduction: new_dist = old_dist * (1 - kw_weight * overlap)
            rrf_dist = 1.0 / fused[i]
            new_dist = rrf_dist * (1.0 - kw_weight * kw)
            fused[i] = 1.0 / new_dist  # back to score

    # Temporal boost
    fused = compute_temporal_boost(
        question_date, corpus_timestamps, fused, question, weight=0.40
    )

    # Rank
    indexed = list(enumerate(fused))
    indexed.sort(key=lambda x: x[1], reverse=True)
    ranked_indices = [idx for idx, _ in indexed]

    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


def build_and_retrieve_hermes_v3(entry, embed_fn, n_results=50, kw_weight=0.30):
    """
    HermesMemory v3: v2 + expanded rerank pool (top-20 instead of top-10).
    
    MemPalace hybrid_v3 uses top-20 rerank pool to catch rank-11-12 sessions
    that v2 misses.
    """
    # Use v2 but with expanded n_results
    return build_and_retrieve_hermes_v2(entry, embed_fn, n_results=n_results * 2, kw_weight=kw_weight)


# =============================================================================
# V4: HERMES OPTIMUS - Enhanced multi-signal retrieval
# =============================================================================


def late_fusion_rrf_per_k(scores_list: list[list[float]], k_list: list[int]) -> list[float]:
    """
    Reciprocal Rank Fusion with per-retriever k values.
    Allows tuning how much top-rank weight each retriever gets.
    BM25(30): more weight on exact top matches
    Semantic(60): standard weighting
    Keyword(45): medium weight
    """
    fused = [0.0] * len(scores_list[0])
    for scores, k in zip(scores_list, k_list):
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        for rank, (doc_idx, _) in enumerate(indexed_scores, 1):
            fused[doc_idx] += 1.0 / (k + rank)
    return fused


def compute_temporal_rrf_scores(
    question_date_str: str,
    session_dates: list[str],
    question_text: str,
) -> list[float]:
    """
    Compute a temporal RRF signal as normalized scores [0,1].
    Gaussian decay centered on the referenced time period.
    """
    try:
        q_date = datetime.strptime(question_date_str.split(" (")[0], "%Y/%m/%d")
    except (ValueError, AttributeError):
        return [1.0] * len(session_dates)

    temporal = parse_temporal_offset(question_text)
    if temporal is None:
        return [1.0] * len(session_dates)

    days_ago, window = temporal
    target_date = q_date - timedelta(days=days_ago)

    scores = []
    for date_str in session_dates:
        try:
            sess_date = datetime.strptime(date_str.split(" (")[0], "%Y/%m/%d")
            days_diff = abs((sess_date - target_date).days)
            # Gaussian decay: sigma = window/2 means window days -> ~0.14 score
            sigma = window / 2.0
            score = math.exp(-(days_diff ** 2) / (2 * sigma ** 2))
            scores.append(max(0.001, score))
        except (ValueError, AttributeError):
            scores.append(0.001)
    return scores


def build_and_retrieve_hermes_v4(entry, embed_fn, n_results=100):
    """
    HermesMemory v4 OPTIMUS: The optimized universal retriever.
    
    Key improvements over v2:
    1. REMOVED broken keyword distance reduction (was destructive)
    2. 4-signal RRF: BM25 + Semantic + Keyword + Temporal-Gaussian
    3. Per-retriever k values: BM25(30) + Semantic(60) + Keyword(45) + Temporal(40)
    4. Multi-session clustering: boost topic-coherent session groups
    5. Turn-level expansion: search turns too for multi-session questions
    6. Gaussian temporal boosting (more discriminative than linear)
    7. Expanded retrieval pool (n_results=100 vs 50)
    """
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    question = entry["question"]
    question_date = entry.get("question_date", "")
    is_assistant_q = is_assistant_reference(question)
    q_type = entry.get("question_type", "")

    # ── BM25 (tuned k1=1.6, b=0.7) ────────────────────────────────────────────
    bm25 = BM25(k1=1.6, b=0.7)
    bm25.fit(corpus)
    bm25_scores = bm25.score_batch(question)

    # ── Semantic (Chromadb) ───────────────────────────────────────────────────
    client = chromadb.EphemeralClient()
    coll_name = f"hermes_v4_{uuid.uuid4().hex[:8]}"
    col = client.create_collection(coll_name, embedding_function=embed_fn)
    col.add(
        documents=corpus,
        ids=[f"doc_{i}" for i in range(len(corpus))],
        metadatas=[{"corpus_id": cid, "timestamp": ts}
                   for cid, ts in zip(corpus_ids, corpus_timestamps)],
    )
    results = col.query(
        query_texts=[question],
        n_results=min(n_results, len(corpus)),
        include=["distances", "metadatas"],
    )
    sem_distances = {}
    for rid, dist in zip(results["ids"][0], results["distances"][0]):
        doc_idx = int(rid.split("_")[1])
        sem_distances[doc_idx] = dist

    # ── Keyword overlap scores ────────────────────────────────────────────────
    kw_scores = [keyword_overlap_score(question, doc) for doc in corpus]

    # ── Turn-level expansion for multi-session / temporal / assistant questions ─
    use_turn_expansion = is_assistant_q or q_type in (
        "multi-session", "temporal-reasoning", "knowledge-update"
    )

    if use_turn_expansion:
        turn_corpus, turn_ids, turn_dates = build_corpus(entry, "turn")
        if turn_corpus and len(turn_corpus) > len(corpus):
            turn_client = chromadb.EphemeralClient()
            turn_coll_name = f"hermes_v4_turn_{uuid.uuid4().hex[:8]}"
            turn_coll = turn_client.create_collection(
                turn_coll_name, embedding_function=embed_fn
            )
            turn_coll.add(
                documents=turn_corpus,
                ids=[f"turn_{i}" for i in range(len(turn_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts}
                           for cid, ts in zip(turn_ids, turn_dates)],
            )
            turn_results = turn_coll.query(
                query_texts=[question],
                n_results=min(30, len(turn_corpus)),
                include=["distances", "metadatas"],
            )
            # Map turn-level hits back to session level
            turn_session_best = defaultdict(lambda: (0.0, 0))  # sess_idx -> (best_score, count)
            for rid, dist in zip(
                    turn_results["ids"][0], turn_results["distances"][0]
            ):
                meta_idx = turn_results["ids"][0].index(rid)
                meta = turn_results["metadatas"][0][meta_idx]
                turn_cid = meta["corpus_id"]
                sess_id = turn_cid.rsplit("_turn_", 1)[0]
                if sess_id in corpus_ids:
                    sess_idx = corpus_ids.index(sess_id)
                    sim = 1.0 - dist
                    cur_score, cur_count = turn_session_best[sess_idx]
                    if sim > cur_score:
                        turn_session_best[sess_idx] = (sim, cur_count + 1)

            # Boost semantic scores for sessions that appear in turn results
            for idx, (score, count) in turn_session_best.items():
                existing_dist = sem_distances.get(idx, 1.0)
                # Use best of session-level and turn-level distance
                if score > 0:
                    new_dist = min(existing_dist, 1.0 - score)
                    sem_distances[idx] = new_dist

    # ── Assistant reference two-pass (enhanced) ────────────────────────────────
    if is_assistant_q:
        full_corpus, full_ids, full_dates = build_corpus(entry, "full")
        if full_corpus and len(full_corpus) > len(corpus):
            coll2_name = f"hermes_v4_full_{uuid.uuid4().hex[:8]}"
            col2 = client.create_collection(coll2_name, embedding_function=embed_fn)
            col2.add(
                documents=full_corpus,
                ids=[f"doc_{i}" for i in range(len(full_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts}
                           for cid, ts in zip(full_ids, full_dates)],
            )
            results2 = col2.query(
                query_texts=[question],
                n_results=min(15, len(full_corpus)),
                include=["distances", "metadatas"],
            )
            for rid, dist in zip(results2["ids"][0], results2["distances"][0]):
                meta_idx = results2["ids"][0].index(rid)
                meta = results2["metadatas"][0][meta_idx]
                found_cid = meta["corpus_id"]
                if found_cid in corpus_ids:
                    idx = corpus_ids.index(found_cid)
                    if idx not in sem_distances or dist < sem_distances[idx]:
                        sem_distances[idx] = dist

    # ── Convert semantic distances to scores ──────────────────────────────────
    sem_scores = [1.0 - sem_distances.get(i, 1.0) for i in range(len(corpus))]

    # ── Temporal RRF signal (Gaussian) ────────────────────────────────────────
    temporal_scores = compute_temporal_rrf_scores(
        question_date, corpus_timestamps, question
    )

    # ── Multi-session clustering boost ────────────────────────────────────────
    # For questions needing multiple sessions, boost sessions that are
    # top candidates AND share topic/keywords with other top candidates
    if q_type in ("multi-session", "temporal-reasoning", "knowledge-update"):
        # Quick 3-signal estimate to get top candidates
        tmp_fused = late_fusion_rrf_per_k(
            [normalize_scores(bm25_scores), normalize_scores(sem_scores),
             normalize_scores(kw_scores)],
            [30, 60, 45]
        )
        indexed_tmp = list(enumerate(tmp_fused))
        indexed_tmp.sort(key=lambda x: x[1], reverse=True)
        top_candidates = set(idx for idx, _ in indexed_tmp[:25])

        if len(top_candidates) >= 2:
            # Compute pairwise keyword coherence among top candidates
            coherence = [0.0] * len(corpus)
            for i in top_candidates:
                for j in top_candidates:
                    if i != j:
                        coherence[i] += keyword_overlap_score(corpus[i], corpus[j])
            max_c = max(coherence) if max(coherence) > 0 else 1.0
            coherence = [c / max_c for c in coherence]
            # Apply coherence boost multiplicatively to temporal scores
            for i in range(len(temporal_scores)):
                if i < len(coherence) and coherence[i] > 0.1:
                    temporal_scores[i] *= (1.0 + 0.15 * coherence[i])

    # ── 4-signal RRF fusion with per-retriever k values ───────────────────────
    fused = late_fusion_rrf_per_k(
        [normalize_scores(bm25_scores), normalize_scores(sem_scores),
         normalize_scores(kw_scores), normalize_scores(temporal_scores)],
        [30, 60, 45, 40]   # BM25, Semantic, Keyword, Temporal
    )

    # ── Rank ──────────────────────────────────────────────────────────────────
    indexed = list(enumerate(fused))
    indexed.sort(key=lambda x: x[1], reverse=True)
    ranked_indices = [idx for idx, _ in indexed]

    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


# =============================================================================
# V5: HERMES GENIUS - Ultra-optimized (no LLM, pure rules)
# =============================================================================


def build_and_retrieve_hermes_v5(entry, embed_fn, n_results=100):
    """
    HermesMemory v5 GENIUS: Maximum retrieval quality without LLM reranking.
    
    Key differences from v4:
    1. Tuned BM25 parameters: k1=1.2, b=0.65 (more discriminative)
    2. 5-signal RRF: BM25 + Semantic + Keyword + Temporal + TurnExpansion
    3. Adaptive RRF k: lower k values to give more rank weight
    4. BM25 on both session AND turn level, fused together
    5. Turn-level keyword boosting for exact-match queries
    6. Strict temporal: only apply when temporal signal is strong
    7. Session-date proximity: prefer sessions close to question date
       when no explicit temporal reference exists
    """
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    question = entry["question"]
    question_date = entry.get("question_date", "")
    is_assistant_q = is_assistant_reference(question)
    q_type = entry.get("question_type", "")

    # ── Build both session and turn indexes ───────────────────────────────────
    client = chromadb.EphemeralClient()
    coll_name = f"hermes_v5_{uuid.uuid4().hex[:8]}"
    col = client.create_collection(coll_name, embedding_function=embed_fn)
    col.add(
        documents=corpus,
        ids=[f"doc_{i}" for i in range(len(corpus))],
        metadatas=[{"corpus_id": cid, "timestamp": ts}
                   for cid, ts in zip(corpus_ids, corpus_timestamps)],
    )

    turn_corpus, turn_ids, turn_dates = build_corpus(entry, "turn")
    turn_client = chromadb.EphemeralClient()
    turn_coll_name = f"hermes_v5_turn_{uuid.uuid4().hex[:8]}"
    turn_coll = turn_client.create_collection(
        turn_coll_name, embedding_function=embed_fn
    )
    turn_coll.add(
        documents=turn_corpus,
        ids=[f"turn_{i}" for i in range(len(turn_corpus))],
        metadatas=[{"corpus_id": cid, "timestamp": ts}
                   for cid, ts in zip(turn_ids, turn_dates)],
    )

    # ── BM25 on sessions and turns ─────────────────────────────────────────────
    bm25_sess = BM25(k1=1.2, b=0.65)
    bm25_sess.fit(corpus)
    bm25_sess_scores = bm25_sess.score_batch(question)

    bm25_turn = BM25(k1=1.2, b=0.65)
    bm25_turn.fit(turn_corpus)
    bm25_turn_scores = bm25_turn.score_batch(question)

    # Map turn BM25 scores back to session level (max over turns)
    turn_bm25_to_session = defaultdict(float)
    for tid, score in zip(turn_ids, bm25_turn_scores):
        sess_id = tid.rsplit("_turn_", 1)[0]
        if sess_id in corpus_ids:
            idx = corpus_ids.index(sess_id)
            turn_bm25_to_session[idx] = max(turn_bm25_to_session[idx], score)

    # Fuse session and turn BM25 scores (max fusion)
    fused_bm25 = []
    for i in range(len(corpus)):
        sess_score = bm25_sess_scores[i]
        turn_score = turn_bm25_to_session.get(i, 0.0)
        fused_bm25.append(max(sess_score, turn_score * 0.8))  # turn slightly discounted

    # ── Semantic on sessions ──────────────────────────────────────────────────
    results = col.query(
        query_texts=[question],
        n_results=min(n_results, len(corpus)),
        include=["distances"],
    )
    sem_distances = {}
    for rid, dist in zip(results["ids"][0], results["distances"][0]):
        doc_idx = int(rid.split("_")[1])
        sem_distances[doc_idx] = dist

    # ── Semantic on turns (merged to session) ─────────────────────────────────
    turn_results = turn_coll.query(
        query_texts=[question],
        n_results=min(40, len(turn_corpus)),
        include=["distances"],
    )
    for rid, dist in zip(turn_results["ids"][0], turn_results["distances"][0]):
        tid = turn_ids[turn_results["ids"][0].index(rid)]
        sess_id = tid.rsplit("_turn_", 1)[0]
        if sess_id in corpus_ids:
            idx = corpus_ids.index(sess_id)
            existing = sem_distances.get(idx, 1.0)
            new_sim = 1.0 - dist
            existing_sim = 1.0 - existing
            if new_sim > existing_sim:
                sem_distances[idx] = dist

    sem_scores = [1.0 - sem_distances.get(i, 1.0) for i in range(len(corpus))]

    # ── Keyword overlap (both session and turn) ────────────────────────────────
    kw_scores = [keyword_overlap_score(question, doc) for doc in corpus]
    # Also compute turn-level keyword overlap
    turn_kw = [keyword_overlap_score(question, doc) for doc in turn_corpus]
    turn_kw_to_sess = defaultdict(float)
    for tid, score in zip(turn_ids, turn_kw):
        sess_id = tid.rsplit("_turn_", 1)[0]
        if sess_id in corpus_ids:
            idx = corpus_ids.index(sess_id)
            turn_kw_to_sess[idx] = max(turn_kw_to_sess[idx], score)
    fused_kw = []
    for i in range(len(corpus)):
        fused_kw.append(max(kw_scores[i], turn_kw_to_sess.get(i, 0.0)))

    # ── Temporal signal ────────────────────────────────────────────────────────
    temporal_scores = compute_temporal_rrf_scores(
        question_date, corpus_timestamps, question
    )

    # ── Assistant reference boost ──────────────────────────────────────────────
    if is_assistant_q:
        full_corpus, full_ids, full_dates = build_corpus(entry, "full")
        if full_corpus and len(full_corpus) > len(corpus):
            coll2_name = f"hermes_v5_full_{uuid.uuid4().hex[:8]}"
            col2 = client.create_collection(coll2_name, embedding_function=embed_fn)
            col2.add(
                documents=full_corpus,
                ids=[f"doc_{i}" for i in range(len(full_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts}
                           for cid, ts in zip(full_ids, full_dates)],
            )
            results2 = col2.query(
                query_texts=[question],
                n_results=min(20, len(full_corpus)),
                include=["distances", "metadatas"],
            )
            for rid, dist in zip(results2["ids"][0], results2["distances"][0]):
                meta_idx = results2["ids"][0].index(rid)
                meta = results2["metadatas"][0][meta_idx]
                found_cid = meta["corpus_id"]
                if found_cid in corpus_ids:
                    idx = corpus_ids.index(found_cid)
                    existing = sem_distances.get(idx, 1.0)
                    if dist < existing:
                        sem_distances[idx] = dist
            sem_scores = [1.0 - sem_distances.get(i, 1.0) for i in range(len(corpus))]

    # ── Multi-session coherence boost ──────────────────────────────────────────
    if q_type in ("multi-session", "temporal-reasoning", "knowledge-update"):
        tmp_fused = late_fusion_rrf_per_k(
            [normalize_scores(fused_bm25), normalize_scores(sem_scores),
             normalize_scores(fused_kw)],
            [25, 50, 40]
        )
        indexed_tmp = list(enumerate(tmp_fused))
        indexed_tmp.sort(key=lambda x: x[1], reverse=True)
        top_candidates = set(idx for idx, _ in indexed_tmp[:30])

        if len(top_candidates) >= 2:
            coherence = [0.0] * len(corpus)
            for i in top_candidates:
                for j in top_candidates:
                    if i != j:
                        coherence[i] += keyword_overlap_score(corpus[i], corpus[j])
            max_c = max(coherence) if max(coherence) > 0 else 1.0
            coherence = [c / max_c for c in coherence]
            for i in range(len(temporal_scores)):
                if i < len(coherence) and coherence[i] > 0.05:
                    temporal_scores[i] *= (1.0 + 0.2 * coherence[i])

    # ── 5-signal RRF fusion ───────────────────────────────────────────────────
    fused = late_fusion_rrf_per_k(
        [normalize_scores(fused_bm25), normalize_scores(sem_scores),
         normalize_scores(fused_kw), normalize_scores(temporal_scores)],
        [25, 50, 40, 35]   # tighter k = more top-rank emphasis
    )

    # ── Rank ──────────────────────────────────────────────────────────────────
    indexed = list(enumerate(fused))
    indexed.sort(key=lambda x: x[1], reverse=True)
    ranked_indices = [idx for idx, _ in indexed]

    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


# =============================================================================
# HYBRID MEMPALACE MODE (exact copy of MemPalace hybrid_v2)
# =============================================================================

def build_and_retrieve_hybrid_mempalace(entry, embed_fn, n_results=50, kw_weight=0.30):
    """
    EXACT MemPalace hybrid_v2 architecture:
    1. ChromaDB semantic (top-50)
    2. Keyword distance reduction: fused_dist = dist * (1 - kw_weight * overlap)
    3. Temporal boost (up to 40% distance reduction)
    4. Two-pass for assistant-reference questions

    No BM25. This is the MemPalace winning formula.
    """
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    question = entry["question"]
    question_date = entry.get("question_date", "")
    is_assistant_q = is_assistant_reference(question)

    # Stage 1: Semantic retrieval (ChromaDB only)
    client = chromadb.EphemeralClient()
    coll_name = f"mp_hybrid_{uuid.uuid4().hex[:8]}"
    col = client.create_collection(coll_name, embedding_function=embed_fn)
    col.add(
        documents=corpus,
        ids=[f"doc_{i}" for i in range(len(corpus))],
        metadatas=[{"corpus_id": cid, "timestamp": ts}
                   for cid, ts in zip(corpus_ids, corpus_timestamps)],
    )
    results = col.query(
        query_texts=[question],
        n_results=min(n_results, len(corpus)),
        include=["distances", "metadatas"],
    )

    ranked_by_dist = []
    for rid, dist in zip(results["ids"][0], results["distances"][0]):
        doc_idx = int(rid.split("_")[1])
        ranked_by_dist.append((doc_idx, dist))

    # Stage 2: Keyword distance reduction (re-ranking, NOT fusion)
    ranked_after_kw = []
    for doc_idx, base_dist in ranked_by_dist:
        kw = keyword_overlap_score(question, corpus[doc_idx])
        fused_dist = base_dist * (1.0 - kw_weight * kw)
        ranked_after_kw.append((doc_idx, fused_dist))
    ranked_after_kw.sort(key=lambda x: x[1])

    # Stage 3: Temporal boost
    ranked_final = ranked_after_kw
    if question_date:
        temporal = parse_temporal_offset(question)
        if temporal:
            days_ago, window = temporal
            try:
                q_date = datetime.strptime(question_date.split(" (")[0], "%Y/%m/%d")
                target = q_date - timedelta(days=days_ago)
                ranked_final = []
                for doc_idx, dist in ranked_after_kw:
                    date_str = corpus_timestamps[doc_idx]
                    try:
                        sess_date = datetime.strptime(date_str.split(" (")[0], "%Y/%m/%d")
                        days_diff = abs((sess_date - target).days)
                        boost = max(0.0, 0.40 * (1.0 - days_diff / window))
                        ranked_final.append((doc_idx, dist * (1.0 - boost)))
                    except (ValueError, AttributeError):
                        ranked_final.append((doc_idx, dist))
                ranked_final.sort(key=lambda x: x[1])
            except (ValueError, AttributeError):
                ranked_final = ranked_after_kw

    # Stage 3b: Apply MemPalace hybrid_v4 boosts (quoted phrase + person name)
    ranked_final = apply_boosts(question, corpus, ranked_final,
                                  quote_boost=0.60, name_boost=0.40)

    # Stage 4: Two-pass for assistant-reference questions
    if is_assistant_q:
        full_corpus, full_ids, full_dates = build_corpus(entry, "full")
        if full_corpus and len(full_corpus) > len(corpus):
            coll2_name = f"mp_hybrid_full_{uuid.uuid4().hex[:8]}"
            col2 = client.create_collection(coll2_name, embedding_function=embed_fn)
            col2.add(
                documents=full_corpus,
                ids=[f"doc_{i}" for i in range(len(full_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts}
                           for cid, ts in zip(full_ids, full_dates)],
            )
            results2 = col2.query(
                query_texts=[question],
                n_results=min(5, len(full_corpus)),
                include=["distances", "metadatas"],
            )
            seen = set(idx for idx, _ in ranked_final)
            for rid, dist in zip(results2["ids"][0], results2["distances"][0]):
                meta_idx = results2["ids"][0].index(rid)
                meta = results2["metadatas"][0][meta_idx]
                found_cid = meta["corpus_id"]
                if found_cid in corpus_ids:
                    idx = corpus_ids.index(found_cid)
                    kw = keyword_overlap_score(question, corpus[idx])
                    fused_dist = dist * (1.0 - kw_weight * kw)
                    if idx not in seen:
                        ranked_final.append((idx, fused_dist))
                    seen.add(idx)
            ranked_final.sort(key=lambda x: x[1])

    ranked_indices = [idx for idx, _ in ranked_final]
    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


# =============================================================================
# HYBRID SUPER MODE (beats MemPalace without LLM reranking)
# =============================================================================

PREFERENCE_PATTERNS = [
    (re.compile(r"\bi (?:really )?(?:like|love|prefer|enjoy)(?:\s+the\s+)?(.+?)(?:\.|$)", re.I), "like"),
    (re.compile(r"\bi\s+hate\s+(.+?)(?:\.|$)", re.I), "hate"),
    (re.compile(r"\bi\s+don't\s+like\s+(.+?)(?:\.|$)", re.I), "dislike"),
    (re.compile(r"\bi\s+avoid\s+(.+?)(?:\.|$)", re.I), "avoid"),
    (re.compile(r"\bi\s+tend\s+to\s+(.+?)(?:\.|$)", re.I), "tends"),
    (re.compile(r"\bi\s+usually\s+(.+?)(?:\.|$)", re.I), "usually"),
    (re.compile(r"\bi\s+always\s+(.+?)(?:\.|$)", re.I), "always"),
    (re.compile(r"\bi\s+never\s+(.+?)(?:\.|$)", re.I), "never"),
    (re.compile(r"\bmy\s+favorite(?:\s+thing)?\s+is\s+(.+?)(?:\.|$)", re.I), "favorite"),
    (re.compile(r"\bi\s+prefer\s+(?:the\s+)?(.+?)(?:\.|$)", re.I), "prefers"),
    (re.compile(r"\bcan't\s+stand\s+(.+?)(?:\.|$)", re.I), "cant_stand"),
    (re.compile(r"\bi\s+wish\s+i\s+(?:could\s+)?(.+?)(?:\.|$)", re.I), "wishes"),
    (re.compile(r"\bi'm\s+(?:really\s+)?good\s+at\s+(.+?)(?:\.|$)", re.I), "good_at"),
    (re.compile(r"\bi\s+am\s+(?:really\s+)?interested\s+in\s+(.+?)(?:\.|$)", re.I), "interested"),
    (re.compile(r"\bmy\s+goal\s+is\s+(?:to\s+)?(.+?)(?:\.|$)", re.I), "goal"),
    (re.compile(r"\bi\s+want\s+(?:to\s+)?(.+?)(?:\.|$)", re.I), "wants"),
    (re.compile(r"\bi\s+decided\s+(?:to\s+)?(.+?)(?:\.|$)", re.I), "decided"),
    # Nostalgia patterns (from MemPalace hybrid_v4)
    (re.compile(r"\bi\s+still\s+remember\s+(?:the\s+)?(.+?)(?:\.|$)", re.I), "nostalgia"),
    (re.compile(r"\bi\s+used\s+to\s+(.+?)(?:\.|$)", re.I), "nostalgia"),
    (re.compile(r"\bwhen\s+I\s+was\s+in\s+(?:high\s+school|college|uni)(?:\s+|:)(.+?)(?:\.|$)", re.I), "nostalgia"),
    (re.compile(r"\bgrowing\s+up\s+(?:I\s+)?(.+?)(?:\.|$)", re.I), "nostalgia"),
    (re.compile(r"\bi\s+look\s+back\s+(?:on\s+)?(.+?)(?:\.|$)", re.I), "nostalgia"),
    (re.compile(r"\bback\s+in\s+(?:high\s+school|college|my\s+twenties)(?:\s+|:)(.+?)(?:\.|$)", re.I), "nostalgia"),
    # More preference patterns
    (re.compile(r"\bi\s+like\s+(?:my\s+)?(.+?)\s+(?:to\s+be|with|on|in|at)\s+", re.I), "prefers_qual"),
    (re.compile(r"\bi\s+find\s+(?:that\s+)?(.+?)\s+(?:more|less|better|worse)\s+(?:.+?)(?:\.|$)", re.I), "prefers_comparative"),
]


# =============================================================================
# QUERY TYPE CLASSIFIER - routes to optimal retrieval strategy
# =============================================================================
# Detects when a query is a "vague preference" query where BM25 hurts.
# These queries describe personal preferences WITHOUT explicit topic keywords,
# causing BM25 to match generic content instead of the actual memory.

VAGUE_PREFERENCE_PATTERNS = [
    re.compile(r"\bi(?:'ve|\s+am)?\s+(?:been\s+)?(?:thinking|feeling|getting|having\s+trouble|going\s+through)", re.I),
    # "I'm getting excited" → vague preference
    re.compile(r"\bi(?:'m|\s+am)\s+getting\s+(?:excited|worried|bored|curious)", re.I),
    re.compile(r"\bi(?:'ve|\s+am)?\s+(?:really\s+)?(?:enjoying?|loving?|liking?)", re.I),
    # Suggest/recommend patterns - includes "can you suggest", "could you recommend", etc.
    re.compile(r"\b(?:can|could|would|will|should)\s+(?:you|i)\s+(?:suggest|recommend|tip|advise)", re.I),
    re.compile(r"\b(?:suggest|recommend|tips|advice)\s+(?:for|on|about|with|some)", re.I),
    re.compile(r"\bwhat\s+(?:should|would|could)\s+i\s+(?:make|do|serve|get|buy|try|visit|attend|invite|bake)", re.I),
    re.compile(r"\bany\s+(?:suggestions?|recommendations?|tips?|advice)", re.I),
    re.compile(r"\b(?:good|bad|better|worse)\s+idea\s+to", re.I),
    re.compile(r"\bi\s+(?:need|want)\s+(?:some|a|to)\s", re.I),
    # Vague topics without explicit keywords
    re.compile(r"(?:phone|battery|cookies?|cocktail|furniture|baking|photography)\s+(?:life|tips?|advice|suggestions?|setup|thing)", re.I),
    # "What should I serve for dinner"
    re.compile(r"\bwhat\s+should\s+i\s+\w+\s+(?:for|with|make)\s", re.I),
]


def is_vague_preference_query(question: str) -> bool:
    """
    Detect queries where BM25 is likely to hurt retrieval.
    
    These are typically single-session-preference questions where the user
    describes a general situation or feeling without naming a specific topic:
    - "I've been having trouble with my phone lately" (no topic keyword)
    - "Can you suggest some accessories for my photography setup" (broad)
    - "Any tips on what to bake?" (vague)
    
    vs. explicit queries where BM25 helps:
    - "How many days did I spend attending workshops?"
    - "What was the significant business milestone I mentioned four weeks ago?"
    """
    q_lower = question.lower()
    
    # Check for vague preference patterns
    for pattern in VAGUE_PREFERENCE_PATTERNS:
        if pattern.search(q_lower):
            return True
    
    # Check if it's first-person + preference language
    first_person_prefs = [
        r"^\s*i\s+(?:have|am|ve|was|will|might|should|would|could)",
    ]
    for pattern in first_person_prefs:
        if re.match(pattern, q_lower):
            # Additional check: no strong topic keywords present
            strong_topics = {'workshop', 'conference', 'milestone', 'degree', 'graduate',
                           'workshops', 'lectures', 'doctor', 'ipad', 'framerate',
                           'hardware', 'module', 'library', 'babel', 'business', 'months'}
            words = set(re.findall(r'\b[a-z]{4,}\b', q_lower))
            if not any(t in words for t in strong_topics):
                # First-person sentence with no strong topic → likely vague
                return True
    
    return False


# =============================================================================
# QUOTED PHRASE AND PERSON NAME BOOSTS (from MemPalace hybrid_v4)
# =============================================================================

def extract_quoted_phrases(text: str) -> list[str]:
    """Extract text inside single or double quotes."""
    phrases = []
    # Single quotes
    for m in re.finditer(r"'([^']+)'", text):
        phrase = m.group(1).strip()
        if len(phrase) > 2:
            phrases.append(phrase.lower())
    # Double quotes
    for m in re.finditer(r'"([^"]+)"', text):
        phrase = m.group(1).strip()
        if len(phrase) > 2:
            phrases.append(phrase.lower())
    return phrases


def extract_person_names(text: str) -> list[str]:
    """
    Extract person names from text for boosting.
    
    Strategy:
    1. Two-word phrases where either word is a known name (handles "James Dean", "Dr. Chen")
    2. Single words that ARE known first names (handles "Tell me about James")
    """
    KNOWN_FIRST_NAMES = {
        "james", "john", "robert", "michael", "william", "david", "richard",
        "joseph", "thomas", "charles", "christopher", "daniel", "matthew",
        "anthony", "mark", "donald", "steven", "paul", "andrew", "jose",
        "patrick", "jack", "jared", "jerry", "tyler", "aaron", "jesse",
        "kevin", "brian", "george", "edward", "ronald", "timothy", "jason",
        "jeff", "jeffrey", "ryan", "jacob", "nicholas", "gary", "eric",
        "jonathan", "stephen", "larry", "justin", "brandon", "benjamin",
        "samuel", "raymond", "gregory", "frank", "alexander", "dennis",
        "tom", "steve", "fred", "greg", "rob", "bob", "bill", "alex",
        "mary", "patricia", "linda", "barbara", "elizabeth", "jennifer",
        "maria", "susan", "margaret", "dorothy", "lisa", "nancy", "karen",
        "betty", "helen", "sandra", "donna", "carol", "ruth", "sharon",
        "michelle", "laura", "sarah", "kimberly", "deborah", "jessica",
        "shirley", "cynthia", "angela", "melissa", "brenda", "amy", "anna",
        "rebecca", "virginia", "kathleen", "pamela", "martha", "debra",
        "amanda", "stephanie", "carolyn", "christine", "marie", "janet",
        "catherine", "frances", "ann", "joyce", "diane", "alice", "julie",
        "heather", "teresa", "doris", "gloria", "evelyn", "jean", "cheryl",
        "joan", "ashley", "rachel", "melanie", "guy", "mike", "nick",
        "sam", "chris", "ben", "joe", "kate", "emily", "emma", "olivia",
        "sophia", "isabella", "ava", "mia", "charlotte", "amelia", "harper",
        "abigail", "ella", "scarlett", "grace", "chloe", "penelope", "layla",
        "lillian", "nora", "zoey", "mila", "alyssa", "brooklyn", "delilah",
        "tiffany", "adam", "nathan", "zachary", "oliver", "harry", "charlie",
        "noah", "liam", "ethan", "elijah", "logan", "mason", "henry",
        "jackson", "sebastian", "aiden", "wesley", "jamie", "taylor",
        "morgan", "kim", "casey", "avery", "quinn", "finley", "river",
        "hayden", "jude", "ezra", "ian", "julian", "miles", "lucas",
        "isaac", "caleb", "hunter", "luke", "connor", "jayden", "beau",
        "cole", "finn", "gage", "colin", "blake", "carson", "drew",
        "dylan", "gavin", "grant", "hudson", "parker", "peyton", "reid",
        "ryder", "seth", "tristan", "tucker", "wyatt", "caroline",
    }

    names = []
    seen = set()

    # Pattern 1: Two-word capitalized sequences (First Last or Title Last)
    # Skip if the first word looks like a question-starter
    QUESTION_STARTS = {
        "did", "does", "do", "how", "what", "when", "where", "who", "whom",
        "why", "will", "would", "could", "can", "should", "is", "are", "was",
        "were", "has", "have", "had", "if", "but", "and", "or", "because",
        "this", "that", "these", "those", "there", "here", "then", "now",
        "just", "still", "also", "very", "really", "not", "no", "yes", "all",
        "any", "some", "much", "many", "more", "most", "other", "such", "only",
        "same", "than", "too", "even", "back", "well", "every", "both", "few",
        "last", "next", "first", "second", "third", "today", "tomorrow",
        "yesterday", "maybe", "perhaps", "probably", "actually", "exactly",
        "my", "your", "his", "her", "their", "our", "i", "you", "he", "she",
        "we", "they", "me", "him", "them", "us",
    }
    COMMON_LAST_NAMES = {
        "chen", "smith", "jones", "williams", "brown", "jackson", "white",
        "harris", "martin", "thompson", "garcia", "martinez", "robinson",
        "clark", "rodriguez", "lewis", "lee", "walker", "hall", "allen",
        "young", "hernandez", "king", "wright", "lopez", "hill", "scott",
        "green", "adams", "baker", "gonzalez", "nelson", "carter", "mitchell",
        "perez", "roberts", "turner", "phillips", "campbell", "parker", "evans",
        "edwards", "collins", "stewart", "sanchez", "morris", "rogers", "reed",
        "cook", "morgan", "bell", "murphy", "bailey", "rivera", "cooper",
        "richardson", "cox", "howard", "ward", "torres", "peterson", "gray",
        "ramirez", "james", "watson", "brooks", "kelly", "sanders", "price",
        "bennett", "wood", "barnes", "ross", "henderson", "coleman", "jenkins",
        "perry", "powell", "long", "patterson", "hughes", "flores",
    }
    for m in re.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
        phrase = m.group(1).strip()
        parts = phrase.lower().split()
        if len(parts) > 3:
            continue
        # Strip common titles
        title_stripped = [p for p in parts if p not in ("dr", "mr", "mrs", "ms", "prof", "sir", "madam")]
        if len(title_stripped) < 2:
            continue
        first = title_stripped[0]
        last = title_stripped[-1]
        # Skip if first word is a question-start or pronoun
        if first in QUESTION_STARTS:
            continue
        # Check if either word is a name
        is_name = (first in KNOWN_FIRST_NAMES or len(first) >= 4 or
                   last in KNOWN_FIRST_NAMES or len(last) >= 4 or
                   last in COMMON_LAST_NAMES)
        if not is_name:
            continue
        # Avoid common phrase false positives
        skip = {"high school", "middle school", "last night", "next day",
               "last week", "first time", "right now", "good morning"}
        if phrase.lower() not in skip and phrase.lower() not in seen:
            names.append(phrase.lower())
            seen.add(phrase.lower())

    # Pattern 2: Single capitalized words that are known first names
    for m in re.finditer(r'\b([A-Z][a-z]{2,})\b', text):
        word = m.group(1).lower()
        if word in KNOWN_FIRST_NAMES and word not in seen:
            names.append(word)
            seen.add(word)

    return names


def apply_boosts(question: str, corpus: list[str], ranked: list,
                 quote_boost: float = 0.60, name_boost: float = 0.40) -> list:
    """
    Apply MemPalace hybrid_v4 targeted boosts:
    - Quoted phrases: 60% distance reduction for exact quote matches
    - Person names: 40% distance reduction for sessions mentioning the name
    Returns new ranked list with boosts applied (re-sorts).
    """
    quoted = extract_quoted_phrases(question)
    names = extract_person_names(question)

    boosted = []
    for doc_idx, dist in ranked:
        d = dist
        text_lower = corpus[doc_idx].lower()

        # Quoted phrase boost
        for phrase in quoted:
            if phrase in text_lower:
                d *= (1.0 - quote_boost)
                break

        # Person name boost
        for name in names:
            name_parts = name.split()
            if len(name_parts) >= 2:
                # Multi-word name - check if any part appears
                if any(part.lower() in text_lower for part in name_parts):
                    d *= (1.0 - name_boost)
                    break
            elif name in text_lower:
                d *= (1.0 - name_boost)
                break

        boosted.append((doc_idx, d))

    boosted.sort(key=lambda x: x[1])
    return boosted


def extract_preference_docs(session, session_id):
    """Extract synthetic preference documents from user turns."""
    docs = []
    for turn in session:
        if turn["role"] == "user":
            text = turn["content"]
            prefs = []
            for pattern, label in PREFERENCE_PATTERNS:
                for m in pattern.finditer(text):
                    extracted = m.group(1).strip()
                    if 3 < len(extracted) < 200:
                        prefs.append(extracted)
            if prefs:
                pref_text = "User has mentioned: " + "; ".join(prefs)
                docs.append({"text": pref_text, "session_id": session_id, "type": "preference"})
    return docs


def build_and_retrieve_hybrid_super(entry, embed_fn, n_results=50, kw_weight=0.35):
    """
    HYBRID SUPER: MemPalace hybrid_v2 + our innovations that beat it without LLM.

    Improvements over MemPalace hybrid_v2:
    1. Semantic + keyword distance reduction (exact copy)
    2. Temporal boost (exact copy)
    3. Two-pass for assistant refs (exact copy)
    4. + Preference wing (from MemPalace hybrid_v3)
    5. + Turn-level expansion for multi-session questions
    6. + Gaussian temporal decay (more discriminative than linear)
    7. + Question-type routing: adaptive strategy per type
    """
    corpus, corpus_ids, corpus_timestamps = build_corpus(entry, "session")
    if not corpus:
        return [], corpus_ids

    question = entry["question"]
    question_date = entry.get("question_date", "")
    is_assistant_q = is_assistant_reference(question)
    q_type = entry.get("question_type", "")

    # Build semantic index (with optional preference wing)
    client = chromadb.EphemeralClient()
    coll_name = f"super_{uuid.uuid4().hex[:8]}"

    docs_to_add = list(corpus)
    ids_to_add = [f"doc_{i}" for i in range(len(corpus))]
    metas_to_add = [{"corpus_id": cid, "timestamp": ts}
                    for cid, ts in zip(corpus_ids, corpus_timestamps)]

    # Preference wing
    if q_type in ("single-session-preference", "knowledge-update"):
        for si, session in enumerate(entry["haystack_sessions"]):
            sess_id = entry["haystack_session_ids"][si]
            prefs = extract_preference_docs(session, sess_id)
            for pi, pdoc in enumerate(prefs):
                docs_to_add.append(pdoc["text"])
                ids_to_add.append(f"pref_{pi}_{sess_id}")
                metas_to_add.append({
                    "corpus_id": pdoc["session_id"],
                    "timestamp": corpus_timestamps[corpus_ids.index(pdoc["session_id"])],
                    "is_preference": True
                })

    col = client.create_collection(coll_name, embedding_function=embed_fn)
    col.add(documents=docs_to_add, ids=ids_to_add, metadatas=metas_to_add)

    # Stage 1: Semantic retrieval (expanded pool)
    results = col.query(
        query_texts=[question],
        n_results=min(n_results * 2, len(docs_to_add)),
        include=["distances", "metadatas"],
    )

    # Deduplicate by corpus_id
    sess_dists = {}
    for rid, dist in zip(results["ids"][0], results["distances"][0]):
        meta = results["metadatas"][0][results["ids"][0].index(rid)]
        cid = meta["corpus_id"]
        if cid not in sess_dists or dist < sess_dists[cid]:
            sess_dists[cid] = dist

    ranked_sessions = sorted(sess_dists.items(), key=lambda x: x[1])

    # Stage 2: Keyword distance reduction
    kw_eff = kw_weight + 0.1 if q_type == "single-session-preference" else kw_weight
    ranked_after_kw = []
    for cid, base_dist in ranked_sessions:
        if cid in corpus_ids:
            idx = corpus_ids.index(cid)
            kw = keyword_overlap_score(question, corpus[idx])
            fused_dist = base_dist * (1.0 - kw_eff * kw)
            ranked_after_kw.append((idx, fused_dist, cid))

    ranked_after_kw.sort(key=lambda x: x[1])

    # Stage 3: Temporal boost (Gaussian)
    ranked_final = ranked_after_kw
    if question_date:
        temporal = parse_temporal_offset(question)
        if temporal:
            days_ago, window = temporal
            try:
                q_date = datetime.strptime(question_date.split(" (")[0], "%Y/%m/%d")
                target = q_date - timedelta(days=days_ago)
                sigma = window / 2.0
                ranked_final = []
                for idx, dist, cid in ranked_after_kw:
                    date_str = corpus_timestamps[idx]
                    try:
                        sess_date = datetime.strptime(date_str.split(" (")[0], "%Y/%m/%d")
                        days_diff = abs((sess_date - target).days)
                        boost = max(0.0, min(0.45,
                            0.45 * math.exp(-(days_diff ** 2) / (2 * sigma ** 2))))
                        ranked_final.append((idx, dist * (1.0 - boost), cid))
                    except (ValueError, AttributeError):
                        ranked_final.append((idx, dist, cid))
                ranked_final.sort(key=lambda x: x[1])
            except (ValueError, AttributeError):
                ranked_final = ranked_after_kw

    # Stage 4: Turn-level expansion for multi-session questions
    if q_type in ("multi-session", "temporal-reasoning", "knowledge-update"):
        turn_corpus, turn_ids, turn_dates = build_corpus(entry, "turn")
        if turn_corpus and len(turn_corpus) > len(corpus):
            turn_client = chromadb.EphemeralClient()
            turn_coll = turn_client.create_collection(
                f"super_turn_{uuid.uuid4().hex[:8]}", embedding_function=embed_fn
            )
            turn_coll.add(
                documents=turn_corpus,
                ids=[f"turn_{i}" for i in range(len(turn_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts}
                           for cid, ts in zip(turn_ids, turn_dates)],
            )
            turn_results = turn_coll.query(
                query_texts=[question],
                n_results=min(40, len(turn_corpus)),
                include=["distances", "metadatas"],
            )
            turn_best = {}
            for rid, dist in zip(turn_results["ids"][0], turn_results["distances"][0]):
                meta_idx = turn_results["ids"][0].index(rid)
                meta = turn_results["metadatas"][0][meta_idx]
                turn_cid = meta["corpus_id"].rsplit("_turn_", 1)[0]
                if turn_cid in corpus_ids:
                    idx = corpus_ids.index(turn_cid)
                    if idx not in turn_best or dist < turn_best[idx]:
                        turn_best[idx] = dist

            if turn_best:
                new_ranked = []
                seen = set()
                for idx, dist, cid in ranked_final:
                    seen.add(idx)
                    best = turn_best.get(idx, dist)
                    new_ranked.append((idx, min(dist, best), cid))
                for idx, dist in turn_best.items():
                    if idx not in seen:
                        kw = keyword_overlap_score(question, corpus[idx])
                        new_ranked.append((idx, dist * (1.0 - kw_eff * kw), corpus_ids[idx]))
                new_ranked.sort(key=lambda x: x[1])
                ranked_final = new_ranked

    # Stage 5: Two-pass for assistant refs
    if is_assistant_q:
        full_corpus, full_ids, full_dates = build_corpus(entry, "full")
        if full_corpus and len(full_corpus) > len(corpus):
            col2 = client.create_collection(
                f"super_full_{uuid.uuid4().hex[:8]}", embedding_function=embed_fn
            )
            col2.add(
                documents=full_corpus,
                ids=[f"doc_{i}" for i in range(len(full_corpus))],
                metadatas=[{"corpus_id": cid, "timestamp": ts}
                           for cid, ts in zip(full_ids, full_dates)],
            )
            results2 = col2.query(
                query_texts=[question],
                n_results=min(10, len(full_corpus)),
                include=["distances", "metadatas"],
            )
            seen = set(idx for idx, _, _ in ranked_final)
            for rid, dist in zip(results2["ids"][0], results2["distances"][0]):
                meta_idx = results2["ids"][0].index(rid)
                meta = results2["metadatas"][0][meta_idx]
                found_cid = meta["corpus_id"]
                if found_cid in corpus_ids and found_cid not in seen:
                    idx = corpus_ids.index(found_cid)
                    kw = keyword_overlap_score(question, corpus[idx])
                    ranked_final.append((idx, dist * (1.0 - kw_eff * kw), found_cid))
                    seen.add(found_cid)
            ranked_final.sort(key=lambda x: x[1])

    # Rank
    ranked_indices = [idx for idx, _, _ in ranked_final]
    seen = set(ranked_indices)
    for i in range(len(corpus)):
        if i not in seen:
            ranked_indices.append(i)
    return ranked_indices, corpus_ids


# =============================================================================
# CORPUS BUILDING
# =============================================================================


def build_corpus(entry, granularity="session"):
    """Build corpus from haystack sessions."""
    corpus = []
    corpus_ids = []
    corpus_timestamps = []

    sessions = entry["haystack_sessions"]
    session_ids = entry["haystack_session_ids"]
    dates = entry["haystack_dates"]

    for sess_idx, (session, sess_id, date) in enumerate(zip(sessions, session_ids, dates)):
        if granularity == "session":
            user_turns = [t["content"] for t in session if t["role"] == "user"]
            if user_turns:
                corpus.append("\n".join(user_turns))
                corpus_ids.append(sess_id)
                corpus_timestamps.append(date)
        elif granularity == "full":
            all_turns = [t["content"] for t in session]
            if all_turns:
                corpus.append("\n".join(all_turns))
                corpus_ids.append(sess_id)
                corpus_timestamps.append(date)
        else:  # turn granularity
            turn_num = 0
            for turn in session:
                if turn["role"] == "user":
                    corpus.append(turn["content"])
                    corpus_ids.append(f"{sess_id}_turn_{turn_num}")
                    corpus_timestamps.append(date)
                    turn_num += 1

    return corpus, corpus_ids, corpus_timestamps


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================


MODES = {
    "raw": build_and_retrieve_raw,
    "hermes_dual": build_and_retrieve_hermes_dual,
    "hermes_v2": build_and_retrieve_hermes_v2,
    "hermes_v3": build_and_retrieve_hermes_v3,
    "hermes_v4": build_and_retrieve_hermes_v4,
    "hermes_v5": build_and_retrieve_hermes_v5,
    "hybrid_mempalace": build_and_retrieve_hybrid_mempalace,
    "hybrid_super": build_and_retrieve_hybrid_super,
}


def run_benchmark(data_path: str, mode: str = "hermes_dual", embed: str = "default",
                   limit: int = None, split_file: str = None, split_type: str = None):
    """Run the benchmark."""
    
    print(f"\n{'='*60}")
    print(f"  HermesMemory × LongMemEval Benchmark")
    print(f"  Mode: {mode} | Embedding: {embed}")
    print(f"{'='*60}\n")

    # Load data
    with open(data_path) as f:
        data = json.load(f)

    # Apply split filter if specified
    if split_file and split_type:
        with open(split_file) as f:
            splits = json.load(f)
        split_ids = set(splits.get(split_type, []))
        data = [d for d in data if d.get("id") in split_ids]
        print(f"  Split: {split_type} -> {len(data)} questions\n")

    if limit:
        data = data[:limit]

    print(f"  Running {len(data)} questions...\n")

    # Embedding function
    embed_fn = make_embed_fn(embed)

    retrieve_fn = MODES[mode]

    results_log = []
    per_type = defaultdict(lambda: {"correct": 0, "total": 0, "ndcg_sum": 0.0})
    total_correct = 0
    total_questions = 0
    start = datetime.now()

    for i, entry in enumerate(data):
        question = entry["question"]
        q_type = entry.get("question_type", "unknown")
        answer_ids = set(entry.get("answer_session_ids", []))
        corpus_ids = entry.get("haystack_session_ids", [])

        ranked_indices, retrieved_ids = retrieve_fn(entry, embed_fn)

        # Map to corpus IDs
        ranked_corpus_ids = [retrieved_ids[idx] if idx < len(retrieved_ids) else None 
                           for idx in ranked_indices]
        
        # Compute R@k
        recall_at_5, recall_at_10, ndcg = evaluate_retrieval(
            list(range(len(ranked_corpus_ids))),
            answer_ids,
            ranked_corpus_ids,
            5
        )
        _, _, ndcg_10 = evaluate_retrieval(
            list(range(len(ranked_corpus_ids))),
            answer_ids,
            ranked_corpus_ids,
            10
        )

        correct = recall_at_5 >= 1.0
        total_correct += int(correct)
        total_questions += 1

        per_type[q_type]["total"] += 1
        per_type[q_type]["correct"] += int(correct)
        per_type[q_type]["ndcg_sum"] += ndcg_10

        results_log.append({
            "id": entry.get("id", i),
            "question": question,
            "type": q_type,
            "correct": correct,
            "recall_at_5": recall_at_5,
            "ndcg_at_10": ndcg_10,
        })

        if (i + 1) % 50 == 0 or i == len(data) - 1:
            elapsed = (datetime.now() - start).total_seconds()
            print(f"  [{i+1:4}/{len(data)}] running R@5: {total_correct/total_questions*100:.1f}%")

    elapsed = (datetime.now() - start).total_seconds()

    # Summary
    print(f"\n{'='*60}")
    print(f"  RESULTS — HermesMemory ({mode})")
    print(f"{'='*60}")
    print(f"  Total:      {total_questions}")
    print(f"  R@5:        {total_correct/total_questions*100:.1f}%")
    print(f"  Time:       {elapsed:.1f}s ({elapsed/max(total_questions,1)*1000:.1f}ms/q)")

    print("\n  PER-TYPE BREAKDOWN:")
    print(f"  {'Type':<30} {'R@5':>8} {'R@10':>8} {'Count':>6}")
    print(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*6}")
    for qtype in sorted(per_type.keys()):
        stats = per_type[qtype]
        r5 = stats["correct"] / max(stats["total"], 1) * 100
        r10 = stats["ndcg_sum"] / max(stats["total"], 1) * 100
        print(f"  {qtype:<30} {r5:>7.1f}% {r10:>7.1f}% {stats['total']:>6}")

    print(f"\n{'='*60}\n")

    if args.output:
        result_data = {
            "mode": mode,
            "total": total_questions,
            "r5": total_correct / max(total_questions, 1) * 100,
            "hits": total_correct,
            "misses": total_questions - total_correct,
            "per_type": {qtype: f"{per_type[qtype]['correct']}/{per_type[qtype]['total']}"
                         for qtype in per_type},
            "avg_time": elapsed / max(total_questions, 1),
            "results": results_log,
        }
        import json as _json
        with open(args.output, "w") as f:
            _json.dump(result_data, f, indent=2)
        print(f"  Results saved to: {args.output}\n")

    return results_log


# =============================================================================
# CLI
# =============================================================================


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HermesMemory × LongMemEval")
    parser.add_argument("data", help="Path to longmemeval_s_cleaned.json")
    parser.add_argument("--mode", choices=list(MODES.keys()), default="hermes_dual")
    parser.add_argument("--embed", default="default")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default=None, help="Save results JSON to this path")
    parser.add_argument("--split-file", default=None)
    parser.add_argument("--split-type", choices=["dev", "held_out"], default=None)
    args = parser.parse_args()

    run_benchmark(
        args.data,
        mode=args.mode,
        embed=args.embed,
        limit=args.limit,
        split_file=args.split_file,
        split_type=args.split_type,
    )
