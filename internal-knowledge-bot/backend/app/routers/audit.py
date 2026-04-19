import csv
import io
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_manager_or_admin
from ..models import AuditEvent, User

router = APIRouter(prefix="/api/audit", tags=["audit"])


def _fetch_events(db: Session, tenant_id: int, limit: int) -> list[dict]:
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .all()
    )

    out = []
    for r in rows:
        try:
            meta = json.loads(r.metadata_json)
        except Exception:
            meta = {}
        out.append(
            {
                "id": r.id,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "actor_user_id": r.actor_user_id,
                "metadata": meta,
                "created_at": r.created_at,
            }
        )
    return out


@router.get("/events")
def list_events(limit: int = 100, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    limit = max(1, min(500, int(limit)))
    return _fetch_events(db, actor.tenant_id, limit)


@router.get("/events/export")
def export_events(
    format: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = 1000,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager_or_admin),
):
    limit = max(1, min(5000, int(limit)))
    events = _fetch_events(db, actor.tenant_id, limit)

    if format == "json":
        return JSONResponse(content=events)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "action", "resource_type", "resource_id", "actor_user_id", "created_at", "metadata_json"])
    for e in events:
        writer.writerow(
            [
                e["id"],
                e["action"],
                e["resource_type"],
                e["resource_id"],
                e["actor_user_id"],
                e["created_at"],
                json.dumps(e["metadata"], ensure_ascii=False),
            ]
        )

    return PlainTextResponse(content=output.getvalue(), media_type="text/csv")
