from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .audit_utils import record_audit
from .document_service import create_document_and_index
from .models import IngestionJob


def process_ingestion_jobs(
    db: Session,
    *,
    limit: int = 10,
    tenant_id: int | None = None,
    actor_user_id: int | None = None,
) -> dict:
    now = datetime.utcnow()
    limit = max(1, min(100, int(limit)))

    query = db.query(IngestionJob).filter(
        IngestionJob.status.in_(["queued", "retry"]),
        ((IngestionJob.next_attempt_at.is_(None)) | (IngestionJob.next_attempt_at <= now)),
    )
    if tenant_id is not None:
        query = query.filter(IngestionJob.tenant_id == tenant_id)

    jobs = query.order_by(IngestionJob.created_at.asc()).limit(limit).all()

    processed = 0
    success = 0
    failed = 0

    for job in jobs:
        processed += 1
        job.status = "processing"
        job.started_at = now
        job.updated_at = now
        db.add(job)
        db.flush()

        try:
            roles = __import__("json").loads(job.roles_allowed_json)
            groups = __import__("json").loads(job.groups_allowed_json)
            tags = __import__("json").loads(job.tags_json)

            doc, _ = create_document_and_index(
                db,
                tenant_id=job.tenant_id,
                created_by_user_id=job.created_by_user_id,
                title=job.title,
                source_type=job.source_type,
                raw_text=job.raw_text,
                roles_allowed=roles,
                groups_allowed=groups,
                tags=tags,
                classification=job.classification,
                source_url=job.source_url,
                freshness_score=job.freshness_score,
            )

            job.document_id = doc.id
            job.status = "completed"
            job.finished_at = datetime.utcnow()
            job.updated_at = job.finished_at
            job.last_error = ""
            db.add(job)

            record_audit(
                db,
                tenant_id=job.tenant_id,
                actor_user_id=actor_user_id,
                action="documents.ingestion_job.completed",
                resource_type="ingestion_job",
                resource_id=str(job.id),
                metadata={"document_id": doc.id},
            )
            success += 1
        except Exception as exc:
            job.attempts += 1
            job.last_error = str(exc)[:1000]
            job.updated_at = datetime.utcnow()
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
            else:
                job.status = "retry"
                delay_minutes = min(60, 2 ** max(0, job.attempts - 1))
                job.next_attempt_at = datetime.utcnow() + timedelta(minutes=delay_minutes)
            db.add(job)
            failed += 1

            record_audit(
                db,
                tenant_id=job.tenant_id,
                actor_user_id=actor_user_id,
                action="documents.ingestion_job.retry" if job.status == "retry" else "documents.ingestion_job.failed",
                resource_type="ingestion_job",
                resource_id=str(job.id),
                metadata={"attempts": job.attempts, "error": job.last_error},
            )

    db.commit()
    return {"processed": processed, "success": success, "failed": failed}
