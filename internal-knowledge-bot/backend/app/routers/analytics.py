import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_manager_or_admin
from ..models import AgentRun, AgentRunStep, AuditEvent, Chunk, Document, Feedback, HandoffTicket, QueryLog, User
from ..run_ledger import usage_today, utc_day_string
from ..schemas import AgentRunOut, AgentRunStepOut, ReplayRunResponse, UsageOverviewOut

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _mark_breach_if_needed(ticket: HandoffTicket) -> bool:
    if ticket.status == "resolved":
        return False
    now = datetime.utcnow()
    if ticket.due_at and now > ticket.due_at and ticket.breached_at is None:
        ticket.breached_at = now
        ticket.status = "breached"
        return True
    return False


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tid = user.tenant_id

    # Keep SLA statuses fresh before aggregation
    open_rows = db.query(HandoffTicket).filter(HandoffTicket.tenant_id == tid, HandoffTicket.status != "resolved").all()
    changed = any(_mark_breach_if_needed(r) for r in open_rows)
    if changed:
        db.commit()

    docs = db.query(func.count(Document.id)).filter(Document.tenant_id == tid).scalar() or 0
    chunks = db.query(func.count(Chunk.id)).filter(Chunk.tenant_id == tid).scalar() or 0
    queries = db.query(func.count(QueryLog.id)).filter(QueryLog.tenant_id == tid).scalar() or 0
    unanswered = db.query(func.count(QueryLog.id)).filter(QueryLog.tenant_id == tid, QueryLog.was_answered.is_(False)).scalar() or 0
    avg_conf = db.query(func.avg(QueryLog.confidence)).filter(QueryLog.tenant_id == tid).scalar() or 0.0
    open_handoffs = db.query(func.count(HandoffTicket.id)).filter(HandoffTicket.tenant_id == tid, HandoffTicket.status != "resolved").scalar() or 0
    breached_handoffs = db.query(func.count(HandoffTicket.id)).filter(HandoffTicket.tenant_id == tid, HandoffTicket.breached_at.is_not(None)).scalar() or 0
    up = db.query(func.count(Feedback.id)).filter(Feedback.tenant_id == tid, Feedback.rating == "up").scalar() or 0
    down = db.query(func.count(Feedback.id)).filter(Feedback.tenant_id == tid, Feedback.rating == "down").scalar() or 0
    keyword_escalations = (
        db.query(func.count(AuditEvent.id))
        .filter(AuditEvent.tenant_id == tid, AuditEvent.action == "policy.keyword_escalation")
        .scalar()
        or 0
    )
    rule_escalations = (
        db.query(func.count(AuditEvent.id))
        .filter(AuditEvent.tenant_id == tid, AuditEvent.action == "policy.rule_escalation")
        .scalar()
        or 0
    )

    acked_count = db.query(func.count(HandoffTicket.id)).filter(HandoffTicket.tenant_id == tid, HandoffTicket.first_response_at.is_not(None)).scalar() or 0
    avg_ack_minutes = (
        db.query(
            func.avg(
                (func.julianday(HandoffTicket.first_response_at) - func.julianday(HandoffTicket.created_at)) * 24.0 * 60.0
            )
        )
        .filter(HandoffTicket.tenant_id == tid, HandoffTicket.first_response_at.is_not(None))
        .scalar()
        or 0.0
    )

    run_count = db.query(func.count(AgentRun.id)).filter(AgentRun.tenant_id == tid).scalar() or 0
    avg_run_duration = db.query(func.avg(AgentRun.duration_ms)).filter(AgentRun.tenant_id == tid).scalar() or 0.0
    failed_runs = db.query(func.count(AgentRun.id)).filter(AgentRun.tenant_id == tid, AgentRun.status == "failed").scalar() or 0

    est_cost_total = db.query(func.sum(QueryLog.estimated_cost_usd)).filter(QueryLog.tenant_id == tid).scalar() or 0.0

    return {
        "documents": docs,
        "chunks": chunks,
        "queries": queries,
        "unanswered_queries": unanswered,
        "answer_rate": round((queries - unanswered) / queries, 4) if queries else 0.0,
        "avg_confidence": round(float(avg_conf), 4),
        "open_handoffs": open_handoffs,
        "breached_handoffs": breached_handoffs,
        "acked_handoffs": acked_count,
        "avg_handoff_ack_minutes": round(float(avg_ack_minutes), 2),
        "keyword_escalations": keyword_escalations,
        "rule_escalations": rule_escalations,
        "feedback": {"up": up, "down": down},
        "runs": run_count,
        "failed_runs": failed_runs,
        "avg_run_duration_ms": round(float(avg_run_duration), 2),
        "estimated_cost_total_usd": round(float(est_cost_total), 8),
    }


@router.get("/usage", response_model=UsageOverviewOut)
def usage(db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    from ..run_ledger import get_or_create_tenant_policy

    policy = get_or_create_tenant_policy(db, actor.tenant_id)
    snap = usage_today(db, actor.tenant_id)
    return UsageOverviewOut(
        day_utc=snap["day_utc"],
        queries_today=snap["queries_today"],
        runs_today=snap["runs_today"],
        estimated_cost_today_usd=snap["estimated_cost_today_usd"],
        query_budget_remaining=max(0, int(policy.daily_query_budget) - snap["queries_today"]),
        run_budget_remaining=max(0, int(policy.daily_run_budget) - snap["runs_today"]),
        cost_budget_remaining_usd=round(max(0.0, float(policy.daily_cost_budget_usd) - snap["estimated_cost_today_usd"]), 8),
    )


@router.get("/runs", response_model=list[AgentRunOut])
def list_runs(limit: int = 50, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    limit = max(1, min(200, int(limit)))
    rows = (
        db.query(AgentRun)
        .filter(AgentRun.tenant_id == actor.tenant_id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
        .all()
    )

    out: list[AgentRunOut] = []
    for r in rows:
        step_rows = (
            db.query(AgentRunStep)
            .filter(AgentRunStep.run_id == r.id)
            .order_by(AgentRunStep.step_order.asc(), AgentRunStep.id.asc())
            .all()
        )
        steps = []
        for s in step_rows:
            try:
                meta = json.loads(s.metadata_json)
            except Exception:
                meta = {}
            steps.append(
                AgentRunStepOut(
                    id=s.id,
                    step_order=s.step_order,
                    name=s.name,
                    status=s.status,
                    metadata=meta,
                    started_at=s.started_at,
                    finished_at=s.finished_at,
                    duration_ms=s.duration_ms,
                )
            )

        try:
            req = json.loads(r.request_json)
        except Exception:
            req = {}
        try:
            resp = json.loads(r.response_json)
        except Exception:
            resp = {}

        out.append(
            AgentRunOut(
                id=r.id,
                endpoint=r.endpoint,
                status=r.status,
                idempotency_key=r.idempotency_key,
                replay_of_run_id=r.replay_of_run_id,
                request=req,
                response=resp,
                error=r.error,
                estimated_input_tokens=r.estimated_input_tokens,
                estimated_output_tokens=r.estimated_output_tokens,
                estimated_cost_usd=r.estimated_cost_usd,
                started_at=r.started_at,
                finished_at=r.finished_at,
                duration_ms=r.duration_ms,
                steps=steps,
            )
        )

    return out


@router.post("/runs/{run_id}/replay", response_model=ReplayRunResponse)
def replay_run(run_id: int, db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    from .ask import ask
    from ..schemas import AskRequest

    source = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.tenant_id == actor.tenant_id).first()
    if not source:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Run not found")

    try:
        request_data = json.loads(source.request_json)
    except Exception:
        request_data = {}

    ask_payload = AskRequest(question=str(request_data.get("question") or ""), top_k=request_data.get("top_k"), idempotency_key="")
    replay_response = ask(ask_payload, db=db, user=actor)

    return ReplayRunResponse(success=True, source_run_id=source.id, replay_run_id=int(replay_response.run_id or 0))


@router.get("/unanswered")
def unanswered(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(QueryLog)
        .filter(QueryLog.tenant_id == user.tenant_id, QueryLog.was_answered.is_(False))
        .order_by(QueryLog.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "question": r.question,
            "confidence": r.confidence,
            "run_id": r.run_id,
            "estimated_cost_usd": r.estimated_cost_usd,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/confidence-buckets")
def confidence_buckets(db: Session = Depends(get_db), actor: User = Depends(require_manager_or_admin)):
    rows = db.query(QueryLog).filter(QueryLog.tenant_id == actor.tenant_id).all()
    buckets = {"0-0.2": 0, "0.2-0.5": 0, "0.5-0.8": 0, "0.8-1.0": 0}
    for r in rows:
        c = float(r.confidence)
        if c < 0.2:
            buckets["0-0.2"] += 1
        elif c < 0.5:
            buckets["0.2-0.5"] += 1
        elif c < 0.8:
            buckets["0.5-0.8"] += 1
        else:
            buckets["0.8-1.0"] += 1
    return buckets
