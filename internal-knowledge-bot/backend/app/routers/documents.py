import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_manager_or_admin
from ..document_service import create_document_and_index, validate_roles
from ..ingest import extract_text_from_bytes
from ..job_runner import process_ingestion_jobs as process_ingestion_jobs_core
from ..models import Chunk, Document, DocumentPolicy, IngestionJob, User
from ..schemas import DocumentOut, DocumentTextCreate, FreshnessRunOut, IngestionJobCreate, IngestionJobOut

router = APIRouter(prefix="/api/documents", tags=["documents"])
settings = get_settings()


def _to_out(db: Session, d: Document) -> DocumentOut:
    chunk_count = db.query(Chunk).filter(Chunk.document_id == d.id).count()
    pol = db.query(DocumentPolicy).filter(DocumentPolicy.document_id == d.id).first()
    groups_allowed = []
    tags = []
    classification = "internal"
    source_url = ""
    freshness_score = 0.5
    freshness_last_checked_at = None
    freshness_last_updated_at = None
    auto_refresh_enabled = False
    freshness_check_interval_hours = 24
    freshness_stale_after_hours = 168
    citation_anchor_mode = "char_offsets"
    if pol:
        try:
            groups_allowed = json.loads(pol.groups_allowed_json)
        except Exception:
            groups_allowed = []
        try:
            tags = json.loads(pol.tags_json)
        except Exception:
            tags = []
        classification = pol.classification
        source_url = pol.source_url
        freshness_score = pol.freshness_score
        freshness_last_checked_at = pol.freshness_last_checked_at
        freshness_last_updated_at = pol.freshness_last_updated_at
        auto_refresh_enabled = pol.auto_refresh_enabled
        freshness_check_interval_hours = pol.freshness_check_interval_hours
        freshness_stale_after_hours = pol.freshness_stale_after_hours
        citation_anchor_mode = pol.citation_anchor_mode

    return DocumentOut(
        id=d.id,
        title=d.title,
        source_type=d.source_type,
        roles_allowed=json.loads(d.roles_allowed_json),
        groups_allowed=groups_allowed,
        tags=tags,
        classification=classification,
        source_url=source_url,
        freshness_score=freshness_score,
        freshness_last_checked_at=freshness_last_checked_at,
        freshness_last_updated_at=freshness_last_updated_at,
        auto_refresh_enabled=auto_refresh_enabled,
        freshness_check_interval_hours=freshness_check_interval_hours,
        freshness_stale_after_hours=freshness_stale_after_hours,
        citation_anchor_mode=citation_anchor_mode,
        chunk_count=chunk_count,
        created_at=d.created_at,
    )


def _job_to_out(row: IngestionJob) -> IngestionJobOut:
    return IngestionJobOut(
        id=row.id,
        status=row.status,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        last_error=row.last_error,
        document_id=row.document_id,
        next_attempt_at=row.next_attempt_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.post("/text", response_model=DocumentOut)
def create_text_document(payload: DocumentTextCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        doc, chunk_count = create_document_and_index(
            db,
            tenant_id=user.tenant_id,
            created_by_user_id=user.id,
            title=payload.title,
            source_type="text",
            raw_text=payload.text,
            roles_allowed=payload.roles_allowed,
            groups_allowed=payload.groups_allowed,
            tags=payload.tags,
            classification=payload.classification,
            source_url=payload.source_url,
            freshness_score=payload.freshness_score,
            auto_refresh_enabled=payload.auto_refresh_enabled,
            freshness_check_interval_hours=payload.freshness_check_interval_hours,
            freshness_stale_after_hours=payload.freshness_stale_after_hours,
            citation_anchor_mode=payload.citation_anchor_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="documents.create_text",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={"chunk_count": chunk_count, "classification": payload.classification},
    )

    db.commit()
    db.refresh(doc)
    return _to_out(db, doc)


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    title: str,
    roles_allowed: str = '["admin","manager","employee","viewer"]',
    groups_allowed: str = "[]",
    tags: str = "[]",
    classification: str = "internal",
    source_url: str = "",
    freshness_score: float = 0.5,
    auto_refresh_enabled: bool = False,
    freshness_check_interval_hours: int = 24,
    freshness_stale_after_hours: int = 168,
    citation_anchor_mode: str = "char_offsets",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    text = extract_text_from_bytes(file.filename or "upload.txt", content)
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text")

    try:
        roles = validate_roles(json.loads(roles_allowed))
        groups = json.loads(groups_allowed)
        tag_list = json.loads(tags)
        assert isinstance(groups, list)
        assert isinstance(tag_list, list)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="roles_allowed/groups_allowed/tags must be JSON lists") from exc

    try:
        doc, chunk_count = create_document_and_index(
            db,
            tenant_id=user.tenant_id,
            created_by_user_id=user.id,
            title=title,
            source_type="upload",
            raw_text=text,
            roles_allowed=roles,
            groups_allowed=groups,
            tags=tag_list,
            classification=classification,
            source_url=source_url,
            freshness_score=freshness_score,
            auto_refresh_enabled=auto_refresh_enabled,
            freshness_check_interval_hours=freshness_check_interval_hours,
            freshness_stale_after_hours=freshness_stale_after_hours,
            citation_anchor_mode=citation_anchor_mode,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="documents.upload",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={"chunk_count": chunk_count, "filename": file.filename or ""},
    )

    db.commit()
    db.refresh(doc)
    return _to_out(db, doc)


@router.post("/ingestion-jobs", response_model=IngestionJobOut)
def create_ingestion_job(payload: IngestionJobCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        roles = validate_roles(payload.roles_allowed)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = IngestionJob(
        tenant_id=user.tenant_id,
        created_by_user_id=user.id,
        title=payload.title.strip(),
        source_type="text",
        raw_text=payload.text,
        roles_allowed_json=json.dumps(roles),
        groups_allowed_json=json.dumps(payload.groups_allowed),
        tags_json=json.dumps(payload.tags),
        classification=payload.classification,
        source_url=payload.source_url,
        freshness_score=max(0.0, min(1.0, payload.freshness_score)),
        status="queued",
        attempts=0,
        max_attempts=payload.max_attempts,
    )
    db.add(job)
    db.flush()

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="documents.ingestion_job.create",
        resource_type="ingestion_job",
        resource_id=str(job.id),
        metadata={},
    )

    db.commit()
    db.refresh(job)
    return _job_to_out(job)


@router.get("/ingestion-jobs", response_model=list[IngestionJobOut])
def list_ingestion_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(IngestionJob)
        .filter(IngestionJob.tenant_id == user.tenant_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(200)
        .all()
    )
    return [_job_to_out(r) for r in rows]


@router.post("/ingestion-jobs/process", response_model=dict)
def process_ingestion_jobs(limit: int = 10, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    return process_ingestion_jobs_core(
        db,
        limit=limit,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
    )


@router.post("/freshness/run", response_model=FreshnessRunOut)
def run_freshness_update(limit: int = 100, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    limit = max(1, min(1000, int(limit)))
    now = datetime.utcnow()
    timeout_seconds = max(1, int(settings.freshness_http_timeout_seconds))

    rows = (
        db.query(DocumentPolicy)
        .filter(DocumentPolicy.tenant_id == actor.tenant_id, DocumentPolicy.auto_refresh_enabled.is_(True))
        .order_by(DocumentPolicy.created_at.desc())
        .limit(limit)
        .all()
    )

    scanned = 0
    updated = 0
    skipped = 0
    errors = 0

    requests = None
    try:
        import requests as _requests

        requests = _requests
    except Exception:
        requests = None

    for pol in rows:
        scanned += 1
        due_by_interval = (
            pol.freshness_last_checked_at is None
            or (now - pol.freshness_last_checked_at) >= timedelta(hours=max(1, pol.freshness_check_interval_hours))
        )
        if not due_by_interval:
            skipped += 1
            continue

        pol.freshness_last_checked_at = now
        db.add(pol)

        if not pol.source_url:
            skipped += 1
            continue

        if requests is None:
            errors += 1
            continue

        try:
            resp = requests.head(pol.source_url, timeout=timeout_seconds, allow_redirects=True)
            if resp.status_code >= 400:
                skipped += 1
                continue
            lm = resp.headers.get("Last-Modified")
            etag = resp.headers.get("ETag")

            stale_hours = max(1, pol.freshness_stale_after_hours)
            age_hours = 0
            if lm:
                from email.utils import parsedate_to_datetime

                try:
                    dt = parsedate_to_datetime(lm)
                    if dt.tzinfo is not None:
                        dt = dt.astimezone(tz=None).replace(tzinfo=None)
                    age_hours = max(0.0, (now - dt).total_seconds() / 3600.0)
                except Exception:
                    age_hours = stale_hours + 1
            elif etag:
                age_hours = stale_hours / 2
            else:
                age_hours = stale_hours + 1

            if age_hours <= stale_hours * 0.5:
                new_score = 1.0
            elif age_hours <= stale_hours:
                new_score = 0.7
            elif age_hours <= stale_hours * 2:
                new_score = 0.4
            else:
                new_score = 0.2

            prev = pol.freshness_score
            pol.freshness_score = max(0.0, min(1.0, float(new_score)))
            if abs(prev - pol.freshness_score) >= 0.01:
                pol.freshness_last_updated_at = now
                updated += 1
            else:
                skipped += 1
            db.add(pol)
        except Exception:
            errors += 1

    record_audit(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="documents.freshness.run",
        resource_type="document_policy",
        resource_id="",
        metadata={"scanned": scanned, "updated": updated, "skipped": skipped, "errors": errors},
    )

    db.commit()
    return FreshnessRunOut(scanned=scanned, updated=updated, skipped=skipped, errors=errors)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = (
        db.query(Document)
        .filter(Document.tenant_id == user.tenant_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [_to_out(db, d) for d in docs]


@router.delete("/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = db.query(Document).filter(Document.id == document_id, Document.tenant_id == user.tenant_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="documents.delete",
        resource_type="document",
        resource_id=str(doc.id),
        metadata={},
    )
    db.delete(doc)
    db.commit()
    return {"success": True}
