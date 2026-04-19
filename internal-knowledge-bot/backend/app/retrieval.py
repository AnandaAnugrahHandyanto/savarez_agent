import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from .config import get_settings
from .embedding import EmbeddingService, cosine_similarity
from .models import Chunk, Document, DocumentPolicy

settings = get_settings()


WORD_RE = re.compile(r"[a-zA-Z0-9_\-]{2,}")


@dataclass
class RankedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    text: str
    score: float
    semantic_score: float
    keyword_score: float
    classification: str
    source_url: str
    chunk_index: int
    start_char: int
    end_char: int
    page_number: int | None
    section_label: str


def parse_json_list(value: str, default: list | None = None) -> list:
    default = default or []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else default
    except Exception:
        return default


def keyword_overlap_score(query: str, text: str) -> float:
    q = set(WORD_RE.findall((query or "").lower()))
    t = set(WORD_RE.findall((text or "").lower()))
    if not q or not t:
        return 0.0
    overlap = q.intersection(t)
    return len(overlap) / max(1, len(q))


def blend_scores(semantic_score: float, keyword_score: float, freshness_score: float) -> float:
    score = (
        semantic_score * settings.hybrid_semantic_weight
        + keyword_score * settings.hybrid_keyword_weight
        + freshness_score * settings.hybrid_freshness_weight
    )
    return max(0.0, min(1.0, float(score)))


def role_allowed(roles_json: str, role: str) -> bool:
    roles = parse_json_list(roles_json, ["admin", "manager", "employee", "viewer"])
    return "all" in roles or role in roles


def group_allowed(groups_json: str, user_group_ids: list[int]) -> bool:
    groups = parse_json_list(groups_json, [])
    if not groups:
        return True
    return len(set(int(g) for g in groups).intersection(set(user_group_ids))) > 0


def retrieve_top_chunks(
    db: Session,
    *,
    tenant_id: int,
    role: str,
    user_group_ids: list[int],
    question: str,
    top_k: int,
) -> list[RankedChunk]:
    qvec = EmbeddingService().embed(question)

    rows = (
        db.query(Chunk, Document, DocumentPolicy)
        .join(Document, Document.id == Chunk.document_id)
        .outerjoin(DocumentPolicy, DocumentPolicy.document_id == Document.id)
        .filter(Chunk.tenant_id == tenant_id)
        .all()
    )

    ranked: list[RankedChunk] = []
    for chunk, doc, doc_policy in rows:
        if not role_allowed(chunk.roles_allowed_json, role):
            continue

        groups_json = "[]"
        freshness = 0.5
        classification = "internal"
        source_url = ""
        if doc_policy is not None:
            groups_json = doc_policy.groups_allowed_json
            freshness = float(doc_policy.freshness_score)
            classification = doc_policy.classification
            source_url = doc_policy.source_url

        if not group_allowed(groups_json, user_group_ids):
            continue

        cvec = json.loads(chunk.embedding_json)
        sem = cosine_similarity(qvec, cvec)
        key = keyword_overlap_score(question, chunk.text)
        blended = blend_scores(sem, key, freshness)

        ranked.append(
            RankedChunk(
                chunk_id=chunk.id,
                document_id=doc.id,
                document_title=doc.title,
                text=chunk.text,
                score=blended,
                semantic_score=float(max(0.0, min(1.0, sem))),
                keyword_score=float(max(0.0, min(1.0, key))),
                classification=classification,
                source_url=source_url,
                chunk_index=int(chunk.chunk_index or 0),
                start_char=int(chunk.start_char or 0),
                end_char=int(chunk.end_char or 0),
                page_number=chunk.page_number,
                section_label=chunk.section_label or "",
            )
        )

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:top_k]


def build_grounded_answer(question: str, ranked_chunks: list[RankedChunk], *, max_citations: int = 3) -> tuple[str, float, bool]:
    if not ranked_chunks:
        return (
            "I couldn't find enough approved source material to answer safely. "
            "Escalate this to a human owner.",
            0.0,
            True,
        )

    used = ranked_chunks[: max(1, min(max_citations, len(ranked_chunks)))]
    confidence = sum(c.score for c in used[:3]) / min(3, len(used))

    snippets = []
    for i, c in enumerate(used, start=1):
        anchor_bits = [f"chunk #{c.chunk_index}", f"chars {c.start_char}-{c.end_char}"]
        if c.page_number:
            anchor_bits.append(f"page {c.page_number}")
        if c.section_label:
            anchor_bits.append(f"section {c.section_label}")
        anchor = " • ".join(anchor_bits)
        snippets.append(f"[{i}] ({anchor}) {c.text[:260].strip()}...")

    answer = (
        "Grounded answer from approved internal knowledge:\n\n"
        + "\n".join(snippets)
        + "\n\nReview with a human for policy-critical decisions."
    )

    confidence = max(0.0, min(1.0, float(confidence)))
    abstained = confidence < 0.10
    return answer, confidence, abstained
