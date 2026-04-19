from sqlalchemy.orm import Session

from .ingest import index_document_chunks
from .models import Document, DocumentPolicy


ALLOWED_ROLES = {"admin", "manager", "employee", "viewer", "all"}


def validate_roles(roles_allowed: list[str]) -> list[str]:
    roles = [str(r).strip().lower() for r in (roles_allowed or []) if str(r).strip()]
    if not roles:
        return ["admin", "manager", "employee", "viewer"]
    invalid = [r for r in roles if r not in ALLOWED_ROLES]
    if invalid:
        raise ValueError(f"Invalid role(s): {', '.join(sorted(set(invalid)))}")
    # stable unique
    out: list[str] = []
    seen = set()
    for r in roles:
        if r in seen:
            continue
        seen.add(r)
        out.append(r)
    return out


def create_document_and_index(
    db: Session,
    *,
    tenant_id: int,
    created_by_user_id: int,
    title: str,
    source_type: str,
    raw_text: str,
    roles_allowed: list[str],
    groups_allowed: list[int],
    tags: list[str],
    classification: str,
    source_url: str,
    freshness_score: float,
    auto_refresh_enabled: bool = False,
    freshness_check_interval_hours: int = 24,
    freshness_stale_after_hours: int = 168,
    citation_anchor_mode: str = "char_offsets",
) -> tuple[Document, int]:
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("Title cannot be empty")

    clean_text = raw_text or ""
    if not clean_text.strip():
        raise ValueError("Text cannot be empty")

    roles = validate_roles(roles_allowed)

    doc = Document(
        tenant_id=tenant_id,
        title=clean_title,
        source_type=source_type,
        roles_allowed_json=__import__("json").dumps(roles),
        raw_text=clean_text,
        created_by_user_id=created_by_user_id,
    )
    db.add(doc)
    db.flush()

    chunk_count = index_document_chunks(
        db,
        tenant_id=tenant_id,
        document_id=doc.id,
        roles_allowed=roles,
        raw_text=clean_text,
    )

    db.add(
        DocumentPolicy(
            tenant_id=tenant_id,
            document_id=doc.id,
            groups_allowed_json=__import__("json").dumps(groups_allowed or []),
            tags_json=__import__("json").dumps(tags or []),
            classification=(classification or "internal").strip() or "internal",
            source_url=(source_url or "").strip(),
            freshness_score=max(0.0, min(1.0, float(freshness_score))),
            auto_refresh_enabled=bool(auto_refresh_enabled),
            freshness_check_interval_hours=max(1, min(24 * 30, int(freshness_check_interval_hours))),
            freshness_stale_after_hours=max(1, min(24 * 365, int(freshness_stale_after_hours))),
            citation_anchor_mode=(citation_anchor_mode or "char_offsets").strip() or "char_offsets",
        )
    )

    return doc, chunk_count
