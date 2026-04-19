from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, require_manager_or_admin
from ..models import HandoffTicket, User
from ..schemas import HandoffCreate, HandoffOut, HandoffResolve

router = APIRouter(prefix="/api/handoffs", tags=["handoff"])
settings = get_settings()


def _mark_breach_if_needed(ticket: HandoffTicket) -> None:
    if ticket.status == "resolved":
        return
    now = datetime.utcnow()
    if ticket.due_at and now > ticket.due_at and ticket.breached_at is None:
        ticket.breached_at = now
        ticket.status = "breached"


def _to_out(ticket: HandoffTicket) -> HandoffOut:
    return HandoffOut(
        id=ticket.id,
        question=ticket.question,
        status=ticket.status,
        resolution=ticket.resolution,
        due_at=ticket.due_at,
        first_response_at=ticket.first_response_at,
        breached_at=ticket.breached_at,
        created_at=ticket.created_at,
        resolved_at=ticket.resolved_at,
    )


@router.post("", response_model=dict)
def create_handoff(payload: HandoffCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sla_minutes = payload.sla_target_minutes or max(1, int(settings.default_handoff_sla_minutes))
    due_at = datetime.utcnow() + timedelta(minutes=sla_minutes)

    ticket = HandoffTicket(
        tenant_id=user.tenant_id,
        created_by_user_id=user.id,
        query_log_id=payload.query_log_id,
        question=payload.question,
        context=payload.context,
        status="open",
        sla_target_minutes=sla_minutes,
        due_at=due_at,
    )
    db.add(ticket)
    db.flush()

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="handoff.create",
        resource_type="handoff",
        resource_id=str(ticket.id),
        metadata={"sla_target_minutes": sla_minutes, "due_at": due_at.isoformat()},
    )

    db.commit()
    db.refresh(ticket)
    return {"success": True, "ticket_id": ticket.id, "due_at": ticket.due_at}


@router.get("", response_model=list[HandoffOut])
def list_handoffs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(HandoffTicket)
        .filter(HandoffTicket.tenant_id == user.tenant_id)
        .order_by(HandoffTicket.created_at.desc())
        .all()
    )

    changed = False
    for r in rows:
        prior = r.status
        _mark_breach_if_needed(r)
        if r.status != prior:
            changed = True
    if changed:
        db.commit()

    return [_to_out(r) for r in rows]


@router.post("/{ticket_id}/ack")
def acknowledge_handoff(
    ticket_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager_or_admin),
):
    ticket = db.query(HandoffTicket).filter(HandoffTicket.id == ticket_id, HandoffTicket.tenant_id == actor.tenant_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.first_response_at is None:
        ticket.first_response_at = datetime.utcnow()
        if ticket.status == "open":
            ticket.status = "in_progress"

    _mark_breach_if_needed(ticket)
    db.add(ticket)

    record_audit(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="handoff.ack",
        resource_type="handoff",
        resource_id=str(ticket.id),
        metadata={},
    )

    db.commit()
    return {"success": True, "status": ticket.status, "first_response_at": ticket.first_response_at}


@router.post("/{ticket_id}/resolve")
def resolve_handoff(
    ticket_id: int,
    payload: HandoffResolve,
    db: Session = Depends(get_db),
    actor: User = Depends(require_manager_or_admin),
):
    ticket = db.query(HandoffTicket).filter(HandoffTicket.id == ticket_id, HandoffTicket.tenant_id == actor.tenant_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.first_response_at is None:
        ticket.first_response_at = datetime.utcnow()

    ticket.status = "resolved"
    ticket.resolution = payload.resolution
    ticket.resolved_at = datetime.utcnow()
    db.add(ticket)

    record_audit(
        db,
        tenant_id=actor.tenant_id,
        actor_user_id=actor.id,
        action="handoff.resolve",
        resource_type="handoff",
        resource_id=str(ticket.id),
        metadata={},
    )

    db.commit()
    return {"success": True}
