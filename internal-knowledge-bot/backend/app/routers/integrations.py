import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..database import get_db
from ..deps import get_current_user, require_manager_or_admin
from ..models import IntegrationConnection, User
from ..schemas import IntegrationConnectRequest

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

SUPPORTED = {
    "slack": "Slack Workspace",
    "notion": "Notion Workspace",
    "gdrive": "Google Drive",
    "webhook": "Custom Webhook",
}


@router.get("")
def list_integrations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(IntegrationConnection).filter(IntegrationConnection.tenant_id == user.tenant_id).order_by(IntegrationConnection.created_at.desc()).all()
    return {
        "supported": [{"provider": k, "label": v} for k, v in SUPPORTED.items()],
        "connected": [
            {
                "id": r.id,
                "provider": r.provider,
                "display_name": r.display_name,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.post("/connect")
def connect(payload: IntegrationConnectRequest, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    if payload.provider not in SUPPORTED:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    row = IntegrationConnection(
        tenant_id=actor.tenant_id,
        provider=payload.provider,
        display_name=payload.display_name,
        status="connected",
        config_json=json.dumps(payload.config),
    )
    db.add(row)
    db.flush()

    record_audit(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="integrations.connect",
        resource_type="integration",
        resource_id=str(row.id),
        metadata={"provider": payload.provider},
    )

    db.commit()
    db.refresh(row)
    return {"success": True, "id": row.id}


@router.post("/{integration_id}/sync")
def sync(integration_id: int, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    row = db.query(IntegrationConnection).filter(IntegrationConnection.id == integration_id, IntegrationConnection.tenant_id == actor.tenant_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Integration not found")

    row.status = "sync_queued"
    db.add(row)

    record_audit(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="integrations.sync",
        resource_type="integration",
        resource_id=str(row.id),
        metadata={},
    )

    db.commit()
    return {"success": True, "integration_id": integration_id, "message": "Sync queued"}
