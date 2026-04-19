import json
from sqlalchemy.orm import Session

from .models import AuditEvent


def record_audit(
    db: Session,
    *,
    tenant_id: int,
    actor_user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str = "",
    metadata: dict | None = None,
) -> None:
    row = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata_json=json.dumps(metadata or {}),
    )
    db.add(row)
