"""Hybrid retrieval and ranking for the holographic memory store."""

from __future__ import annotations

import math
from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING

from .embeddings import bytes_to_vector, cosine_similarity
from .enrichment import enrich_fact

if TYPE_CHECKING:
    from .store import MemoryStore

try:
    from . import holographic as hrr
except ImportError:
    import holographic as hrr  # type: ignore[no-redef]

_MAX_SEMANTIC_SCAN = 1000


class FactRetriever:
    """Hybrid retrieval with explainable score breakdowns."""

    def __init__(
        self,
        store: MemoryStore,
        temporal_decay_half_life: int = 45,
        fts_weight: float = 0.6,
        jaccard_weight: float = 0.4,
        hrr_weight: float = 0.45,
        hrr_dim: int = 1024,
        embedding_weight: float = 0.55,
        semantic_weight: float = 0.35,
        keyword_weight: float = 0.25,
        recency_weight: float = 0.15,
        salience_weight: float = 0.15,
        confidence_weight: float = 0.10,
    ):
        self.store = store
        self.half_life = temporal_decay_half_life
        self.hrr_dim = hrr_dim

        if hrr_weight > 0 and not hrr._HAS_NUMPY:
            hrr_weight = 0.0

        self.fts_weight = fts_weight
        self.jaccard_weight = jaccard_weight
        self.hrr_weight = hrr_weight
        self.embedding_weight = embedding_weight
        self.rank_weights = {
            "semantic": semantic_weight,
            "keyword": keyword_weight,
            "recency": recency_weight,
            "salience": salience_weight,
            "confidence": confidence_weight,
        }

    def search(
        self,
        query: str,
        category: str | None = None,
        min_trust: float = 0.3,
        limit: int = 10,
        debug: bool = False,
    ) -> list[dict]:
        """Hybrid retrieval with semantic and keyword candidate generation."""
        query = (query or "").strip()
        if not query:
            return []

        query_tokens = self._tokenize(query)
        query_meta = enrich_fact(query, category=category or "general", source_channel="query")
        query_embedding = self.store._embedding_provider.embed_one(query)
        query_hrr = hrr.encode_text(query, self.hrr_dim) if hrr._HAS_NUMPY else None

        candidate_map: dict[int, dict] = {}
        for candidate in self._fts_candidates(query, category, min_trust, max(limit * 4, 20)):
            candidate_map[candidate["fact_id"]] = candidate

        for candidate in self._semantic_candidates(
            category=category,
            min_trust=min_trust,
            limit=max(limit * 6, 24),
            query_embedding=query_embedding,
            query_hrr=query_hrr,
        ):
            existing = candidate_map.get(candidate["fact_id"])
            if existing:
                existing.update({k: v for k, v in candidate.items() if k not in existing or v})
            else:
                candidate_map[candidate["fact_id"]] = candidate

        scored: list[dict] = []
        for candidate in candidate_map.values():
            breakdown = self._score_fact(
                candidate,
                query=query,
                query_tokens=query_tokens,
                query_meta=query_meta.to_dict(),
                query_embedding=query_embedding,
                query_hrr=query_hrr,
            )
            normalized = self._normalize_fact(candidate)
            normalized["score"] = breakdown["final_score"]
            if debug:
                normalized["debug"] = self._build_debug_payload(
                    normalized,
                    breakdown,
                    query_tokens=query_tokens,
                    query_meta=query_meta.to_dict(),
                )
            scored.append(normalized)

        scored.sort(key=lambda fact: fact["score"], reverse=True)
        results = scored[:limit]
        self._mark_retrieved(results)
        return results

    def probe(
        self,
        entity: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        if not hrr._HAS_NUMPY:
            return self.search(entity, category=category, limit=limit)

        conn = self.store._conn
        role_entity = hrr.encode_atom("__hrr_role_entity__", self.hrr_dim)
        entity_vec = hrr.encode_atom(entity.lower(), self.hrr_dim)
        probe_key = hrr.bind(entity_vec, role_entity)

        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT * FROM facts
            {where}
            """,
            params,
        ).fetchall()
        if not rows:
            return self.search(entity, category=category, limit=limit)

        role_content = hrr.encode_atom("__hrr_role_content__", self.hrr_dim)
        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))
            residual = hrr.unbind(fact_vec, probe_key)
            content_vec = hrr.bind(hrr.encode_text(fact["content"], self.hrr_dim), role_content)
            sim = hrr.similarity(residual, content_vec)
            normalized = self._normalize_fact(fact)
            normalized["score"] = ((sim + 1.0) / 2.0) * normalized["trust_score"]
            scored.append(normalized)

        scored.sort(key=lambda fact: fact["score"], reverse=True)
        return scored[:limit]

    def related(
        self,
        entity: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        if not hrr._HAS_NUMPY:
            return self.search(entity, category=category, limit=limit)

        conn = self.store._conn
        entity_vec = hrr.encode_atom(entity.lower(), self.hrr_dim)

        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT * FROM facts
            {where}
            """,
            params,
        ).fetchall()
        if not rows:
            return self.search(entity, category=category, limit=limit)

        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))
            residual = hrr.unbind(fact_vec, entity_vec)
            role_entity = hrr.encode_atom("__hrr_role_entity__", self.hrr_dim)
            role_content = hrr.encode_atom("__hrr_role_content__", self.hrr_dim)
            best_sim = max(
                hrr.similarity(residual, role_entity),
                hrr.similarity(residual, role_content),
            )
            normalized = self._normalize_fact(fact)
            normalized["score"] = ((best_sim + 1.0) / 2.0) * normalized["trust_score"]
            scored.append(normalized)

        scored.sort(key=lambda fact: fact["score"], reverse=True)
        return scored[:limit]

    def reason(
        self,
        entities: list[str],
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        if not hrr._HAS_NUMPY or not entities:
            return self.search(" ".join(entities), category=category, limit=limit)

        conn = self.store._conn
        role_entity = hrr.encode_atom("__hrr_role_entity__", self.hrr_dim)
        probe_keys = []
        for entity in entities:
            entity_vec = hrr.encode_atom(entity.lower(), self.hrr_dim)
            probe_keys.append(hrr.bind(entity_vec, role_entity))

        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT * FROM facts
            {where}
            """,
            params,
        ).fetchall()
        if not rows:
            return self.search(" ".join(entities), category=category, limit=limit)

        role_content = hrr.encode_atom("__hrr_role_content__", self.hrr_dim)
        scored = []
        for row in rows:
            fact = dict(row)
            fact_vec = hrr.bytes_to_phases(fact.pop("hrr_vector"))
            entity_scores = []
            for probe_key in probe_keys:
                residual = hrr.unbind(fact_vec, probe_key)
                entity_scores.append(hrr.similarity(residual, role_content))
            normalized = self._normalize_fact(fact)
            normalized["score"] = ((min(entity_scores) + 1.0) / 2.0) * normalized["trust_score"]
            scored.append(normalized)

        scored.sort(key=lambda fact: fact["score"], reverse=True)
        return scored[:limit]

    def contradict(
        self,
        category: str | None = None,
        threshold: float = 0.3,
        limit: int = 10,
    ) -> list[dict]:
        if not hrr._HAS_NUMPY:
            return []

        conn = self.store._conn
        where = "WHERE hrr_vector IS NOT NULL"
        params: list = []
        if category:
            where += " AND category = ?"
            params.append(category)

        rows = conn.execute(
            f"""
            SELECT * FROM facts
            {where}
            """,
            params,
        ).fetchall()
        if len(rows) < 2:
            return []

        if len(rows) > 500:
            rows = sorted(rows, key=lambda row: row["updated_at"] or row["created_at"], reverse=True)[:500]

        fact_entities: dict[int, set[str]] = {}
        for row in rows:
            metadata = self._parse_metadata(row["metadata_json"])
            fact_entities[row["fact_id"]] = {
                value.lower()
                for value in metadata.get("entity_keys", metadata.get("entities", []))
            }

        contradictions = []
        facts = [dict(row) for row in rows]
        for index, left in enumerate(facts):
            for right in facts[index + 1:]:
                left_entities = fact_entities.get(left["fact_id"], set())
                right_entities = fact_entities.get(right["fact_id"], set())
                if not left_entities or not right_entities:
                    continue

                entity_overlap = len(left_entities & right_entities) / len(left_entities | right_entities)
                if entity_overlap < 0.3:
                    continue

                left_vec = hrr.bytes_to_phases(left["hrr_vector"])
                right_vec = hrr.bytes_to_phases(right["hrr_vector"])
                content_similarity = hrr.similarity(left_vec, right_vec)
                contradiction_score = entity_overlap * (1.0 - ((content_similarity + 1.0) / 2.0))
                if contradiction_score >= threshold:
                    left_clean = self._normalize_fact(left)
                    right_clean = self._normalize_fact(right)
                    contradictions.append({
                        "fact_a": left_clean,
                        "fact_b": right_clean,
                        "entity_overlap": round(entity_overlap, 3),
                        "content_similarity": round(content_similarity, 3),
                        "contradiction_score": round(contradiction_score, 3),
                        "shared_entities": sorted(left_entities & right_entities),
                    })

        contradictions.sort(key=lambda item: item["contradiction_score"], reverse=True)
        return contradictions[:limit]

    # ------------------------------------------------------------------
    # Candidate generation and scoring
    # ------------------------------------------------------------------

    def _semantic_candidates(
        self,
        *,
        category: str | None,
        min_trust: float,
        limit: int,
        query_embedding: list[float] | None,
        query_hrr,
    ) -> list[dict]:
        if not query_embedding and query_hrr is None:
            return []

        conn = self.store._conn
        params: list = [min_trust]
        where_clauses = ["trust_score >= ?"]
        if category:
            where_clauses.append("category = ?")
            params.append(category)
        where_clauses.append("(hrr_vector IS NOT NULL OR embedding_vector IS NOT NULL)")
        where_sql = " AND ".join(where_clauses)

        rows = conn.execute(
            f"""
            SELECT * FROM facts
            WHERE {where_sql}
            ORDER BY salience_score DESC, updated_at DESC
            LIMIT ?
            """,
            params + [_MAX_SEMANTIC_SCAN],
        ).fetchall()

        scored = []
        for row in rows:
            candidate = dict(row)
            semantic_hrr = 0.0
            semantic_embedding = 0.0

            if query_hrr is not None and candidate.get("hrr_vector"):
                fact_hrr = hrr.bytes_to_phases(candidate["hrr_vector"])
                semantic_hrr = (hrr.similarity(query_hrr, fact_hrr) + 1.0) / 2.0

            if query_embedding and candidate.get("embedding_vector"):
                fact_embedding = bytes_to_vector(candidate["embedding_vector"])
                if fact_embedding and len(fact_embedding) == len(query_embedding):
                    semantic_embedding = (cosine_similarity(query_embedding, fact_embedding) + 1.0) / 2.0

            semantic_score = self._combine_semantic(semantic_hrr, semantic_embedding)
            if semantic_score <= 0.0:
                continue

            candidate["semantic_hrr"] = semantic_hrr
            candidate["semantic_embedding"] = semantic_embedding
            candidate["semantic_score"] = semantic_score
            scored.append(candidate)

        scored.sort(key=lambda item: item.get("semantic_score", 0.0), reverse=True)
        return scored[:limit]

    def _score_fact(
        self,
        fact: dict,
        *,
        query: str,
        query_tokens: set[str],
        query_meta: dict,
        query_embedding: list[float] | None,
        query_hrr,
    ) -> dict:
        keyword_jaccard = self._jaccard_similarity(query_tokens, self._tokenize(fact["content"] + " " + fact.get("tags", "")))
        fts_score = float(fact.get("fts_score", 0.0))
        keyword_score = self._combine_keyword(fts_score, keyword_jaccard)

        semantic_hrr = float(fact.get("semantic_hrr", 0.0))
        semantic_embedding = float(fact.get("semantic_embedding", 0.0))

        if semantic_hrr <= 0.0 and query_hrr is not None and fact.get("hrr_vector"):
            fact_hrr = hrr.bytes_to_phases(fact["hrr_vector"])
            semantic_hrr = (hrr.similarity(query_hrr, fact_hrr) + 1.0) / 2.0

        if semantic_embedding <= 0.0 and query_embedding and fact.get("embedding_vector"):
            fact_embedding = bytes_to_vector(fact["embedding_vector"])
            if fact_embedding and len(fact_embedding) == len(query_embedding):
                semantic_embedding = (cosine_similarity(query_embedding, fact_embedding) + 1.0) / 2.0

        semantic_score = self._combine_semantic(semantic_hrr, semantic_embedding)
        recency_score = self._recency_score(fact.get("updated_at") or fact.get("created_at"))
        confidence_score = _mean((fact.get("source_confidence", 0.5), fact.get("trust_score", 0.5)))
        salience_score = float(fact.get("salience_score", 0.5))

        component_scores = {
            "semantic": semantic_score,
            "keyword": keyword_score,
            "recency": recency_score,
            "salience": salience_score,
            "confidence": confidence_score,
        }

        active_weights = {}
        for component, weight in self.rank_weights.items():
            if weight <= 0:
                continue
            if component == "semantic" and semantic_score <= 0.0:
                continue
            active_weights[component] = weight

        if not active_weights:
            final_score = max(keyword_score, salience_score, confidence_score)
        else:
            total_weight = sum(active_weights.values())
            weighted_sum = sum(component_scores[name] * weight for name, weight in active_weights.items())
            final_score = weighted_sum / total_weight if total_weight > 0 else 0.0

        return {
            "final_score": final_score,
            "semantic_score": semantic_score,
            "semantic_hrr": semantic_hrr,
            "semantic_embedding": semantic_embedding,
            "keyword_score": keyword_score,
            "fts_score": fts_score,
            "keyword_jaccard": keyword_jaccard,
            "recency_score": recency_score,
            "salience_score": salience_score,
            "confidence_score": confidence_score,
            "active_weights": active_weights,
            "query": query,
            "query_meta": query_meta,
        }

    def _build_debug_payload(
        self,
        fact: dict,
        breakdown: dict,
        *,
        query_tokens: set[str],
        query_meta: dict,
    ) -> dict:
        metadata = fact.get("metadata", {})
        matched_entities = sorted(
            set(query_meta.get("entities", [])) & set(metadata.get("entities", []))
        )
        if not matched_entities:
            matched_entities = sorted(
                set(query_meta.get("entity_keys", [])) & set(metadata.get("entity_keys", []))
            )

        matched_topics = sorted(set(query_meta.get("topics", [])) & set(metadata.get("topics", [])))
        if not matched_topics:
            matched_topics = sorted(
                set(query_meta.get("topic_keys", [])) & set(metadata.get("topic_keys", []))
            )

        matched_clusters = sorted(
            set(query_meta.get("cluster_keys", [])) & set(metadata.get("cluster_keys", []))
        )
        matched_terms = sorted(query_tokens & self._tokenize(fact["content"] + " " + fact.get("tags", "")))
        links = self.store.get_fact_links(fact["fact_id"], limit=5)

        why: list[str] = []
        if breakdown["semantic_score"] > 0.6:
            semantic_parts = []
            if breakdown["semantic_embedding"] > 0.0:
                semantic_parts.append(f"embedding {breakdown['semantic_embedding']:.2f}")
            if breakdown["semantic_hrr"] > 0.0:
                semantic_parts.append(f"hrr {breakdown['semantic_hrr']:.2f}")
            why.append("semantic match via " + ", ".join(semantic_parts))
        if breakdown["keyword_score"] > 0.15:
            why.append(
                f"keyword overlap fts={breakdown['fts_score']:.2f}, jaccard={breakdown['keyword_jaccard']:.2f}"
            )
        if matched_entities:
            why.append("matched entities: " + ", ".join(matched_entities[:4]))
        if matched_topics:
            why.append("matched topics: " + ", ".join(matched_topics[:4]))
        if matched_clusters:
            why.append("matched clusters: " + ", ".join(matched_clusters[:4]))
        if links:
            why.append("linked memories: " + ", ".join(str(link["linked_fact_id"]) for link in links[:3]))

        return {
            "why": why,
            "score_breakdown": {
                "semantic": round(breakdown["semantic_score"], 4),
                "keyword": round(breakdown["keyword_score"], 4),
                "recency": round(breakdown["recency_score"], 4),
                "salience": round(breakdown["salience_score"], 4),
                "confidence": round(breakdown["confidence_score"], 4),
                "weighted": {
                    name: round(weight, 4)
                    for name, weight in breakdown["active_weights"].items()
                },
            },
            "matched_entities": matched_entities,
            "matched_topics": matched_topics,
            "matched_clusters": matched_clusters,
            "matched_terms": matched_terms,
            "source_channel": fact.get("source_channel", ""),
            "recency_contribution": round(
                breakdown["recency_score"] * breakdown["active_weights"].get("recency", 0.0),
                4,
            ),
            "related_memory_ids": [link["linked_fact_id"] for link in links],
        }

    def _mark_retrieved(self, facts: list[dict]) -> None:
        if not facts:
            return
        ids = [fact["fact_id"] for fact in facts]
        placeholders = ",".join("?" * len(ids))
        self.store._conn.execute(
            f"UPDATE facts SET retrieval_count = retrieval_count + 1 WHERE fact_id IN ({placeholders})",
            ids,
        )
        self.store._conn.commit()

    def _normalize_fact(self, row: dict) -> dict:
        fact = dict(row)
        fact["metadata"] = self._parse_metadata(fact.get("metadata_json"))
        fact.pop("metadata_json", None)
        fact.pop("hrr_vector", None)
        fact.pop("embedding_vector", None)
        return fact

    @staticmethod
    def _parse_metadata(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _combine_keyword(self, fts_score: float, jaccard_score: float) -> float:
        weight_total = self.fts_weight + self.jaccard_weight
        if weight_total <= 0:
            return 0.0
        return ((fts_score * self.fts_weight) + (jaccard_score * self.jaccard_weight)) / weight_total

    def _combine_semantic(self, hrr_score: float, embedding_score: float) -> float:
        weights = []
        if hrr_score > 0.0 and self.hrr_weight > 0:
            weights.append((hrr_score, self.hrr_weight))
        if embedding_score > 0.0 and self.embedding_weight > 0:
            weights.append((embedding_score, self.embedding_weight))
        if not weights:
            return 0.0
        total = sum(weight for _, weight in weights)
        return sum(score * weight for score, weight in weights) / total

    def _fts_candidates(
        self,
        query: str,
        category: str | None,
        min_trust: float,
        limit: int,
    ) -> list[dict]:
        conn = self.store._conn
        params: list = [query]
        where_clauses = ["facts_fts MATCH ?"]
        if category:
            where_clauses.append("f.category = ?")
            params.append(category)
        where_clauses.append("f.trust_score >= ?")
        params.append(min_trust)
        where_sql = " AND ".join(where_clauses)

        try:
            rows = conn.execute(
                f"""
                SELECT f.*, facts_fts.rank AS fts_rank_raw
                FROM facts_fts
                JOIN facts f ON f.fact_id = facts_fts.rowid
                WHERE {where_sql}
                ORDER BY facts_fts.rank
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
        except Exception:
            return []

        if not rows:
            return []

        raw_ranks = [abs(row["fts_rank_raw"]) for row in rows]
        max_rank = max(raw_ranks) if raw_ranks else 1.0
        max_rank = max(max_rank, 1e-6)

        results = []
        for row, raw_rank in zip(rows, raw_ranks):
            fact = dict(row)
            fact.pop("fts_rank_raw", None)
            fact["fts_score"] = max(0.0, 1.0 - (raw_rank / max_rank))
            results.append(fact)
        return results

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        if not text:
            return set()
        tokens = set()
        for word in text.lower().split():
            cleaned = word.strip(".,;:!?\"'()[]{}#@<>")
            if cleaned:
                tokens.add(cleaned)
        return tokens

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        if not set_a or not set_b:
            return 0.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    def _recency_score(self, timestamp_str: str | None) -> float:
        if not self.half_life or not timestamp_str:
            return 0.0

        try:
            timestamp = datetime.fromisoformat(str(timestamp_str).replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - timestamp).total_seconds() / 86400
            if age_days < 0:
                return 1.0
            return math.pow(0.5, age_days / self.half_life)
        except (ValueError, TypeError):
            return 0.0


def _mean(values: tuple[float, ...]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
