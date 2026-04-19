import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..config import get_settings
from ..database import get_db
from ..deps import get_current_user, get_user_group_ids
from ..models import QueryLog, User
from ..policy import evaluate_handoff_decision, redact_pii
from ..retrieval import build_grounded_answer, retrieve_top_chunks
from ..run_ledger import (
    add_step,
    assert_budget_available,
    canonical_request_hash,
    create_run,
    enforce_budget,
    estimate_cost_usd,
    estimate_tokens,
    find_idempotent_response,
    finish_run,
    get_or_create_tenant_policy,
    upsert_idempotent_response,
)
from ..schemas import AskRequest, AskResponse, Citation, FeedbackCreate

settings = get_settings()
router = APIRouter(prefix="/api", tags=["ask"])


def _load_list(raw: str) -> list:
    try:
        value = json.loads(raw)
        if isinstance(value, list):
            return value
    except Exception:
        pass
    return []


@router.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policy = get_or_create_tenant_policy(db, user.tenant_id)

    # enforce question size early
    if len(payload.question or "") > int(policy.max_question_chars):
        raise HTTPException(status_code=400, detail=f"Question exceeds max length ({policy.max_question_chars})")

    idempotency_key = (payload.idempotency_key or "").strip()
    request_payload = {
        "question": payload.question,
        "top_k": payload.top_k,
    }
    request_hash = canonical_request_hash(request_payload)

    prior_response, prior_run_id, _ = find_idempotent_response(
        db,
        tenant_id=user.tenant_id,
        endpoint="/api/ask",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )
    if prior_response is not None:
        try:
            return AskResponse(**prior_response)
        except Exception:
            # fallback if schema changed
            return AskResponse(
                **{
                    **prior_response,
                    "run_id": prior_run_id,
                    "run_status": "replayed",
                }
            )

    # budget check before opening a new run
    usage_snapshot = enforce_budget(db, user)
    assert_budget_available(usage_snapshot)

    run = create_run(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        endpoint="/api/ask",
        idempotency_key=idempotency_key,
        request_payload=request_payload,
    )

    top_k = payload.top_k or settings.top_k_default
    top_k = max(1, min(int(policy.max_top_k), max(1, min(20, top_k))))

    try:
        add_step(db, run_id=run.id, step_order=1, name="validate_and_budget", status="completed", metadata=usage_snapshot)

        user_group_ids = get_user_group_ids(db, tenant_id=user.tenant_id, user_id=user.id)

        add_step(
            db,
            run_id=run.id,
            step_order=2,
            name="retrieve",
            status="running",
            metadata={"top_k": top_k, "group_count": len(user_group_ids)},
        )

        ranked = retrieve_top_chunks(
            db,
            tenant_id=user.tenant_id,
            role=user.role,
            user_group_ids=user_group_ids,
            question=payload.question,
            top_k=top_k,
        )

        add_step(
            db,
            run_id=run.id,
            step_order=3,
            name="critic",
            status="completed",
            metadata={"retrieved_count": len(ranked)},
        )

        answer, confidence, abstained = build_grounded_answer(
            payload.question,
            ranked,
            max_citations=max(1, min(10, policy.max_citations)),
        )

        force_keywords = _load_list(policy.force_handoff_keywords_json)
        policy_rules = _load_list(policy.policy_rules_json)

        primary_classification = ranked[0].classification if ranked else "internal"

        decision = evaluate_handoff_decision(
            question=payload.question,
            confidence=confidence,
            min_confidence=policy.min_confidence,
            force_keywords=force_keywords,
            rules=policy_rules,
            answer=answer,
            classification=primary_classification,
            role=user.role,
        )

        add_step(
            db,
            run_id=run.id,
            step_order=4,
            name="repair",
            status="completed",
            metadata={
                "matched_keywords": decision.matched_keywords,
                "matched_rules": decision.matched_rules,
                "final_action": decision.final_action,
            },
        )

        if policy.pii_redaction_enabled or decision.final_action == "redact":
            answer = redact_pii(answer)

        was_answered = len(ranked) > 0 and not decision.handoff_recommended and not abstained and decision.final_action != "deny"

        if decision.final_action == "deny":
            answer = "This request is blocked by tenant policy and has been escalated to a human owner."

        input_tokens = estimate_tokens(payload.question)
        output_tokens = estimate_tokens(answer)
        estimated_cost = estimate_cost_usd(input_tokens, output_tokens)

        log = QueryLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            run_id=run.id,
            question=payload.question,
            answer=answer,
            confidence=confidence,
            was_answered=was_answered,
            estimated_input_tokens=input_tokens,
            estimated_output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost,
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.flush()

        action = "ask.answer"
        if len(decision.matched_keywords) > 0:
            action = "policy.keyword_escalation"
        elif len(decision.matched_rules) > 0:
            action = "policy.rule_escalation"
        elif decision.handoff_recommended:
            action = "policy.low_confidence_escalation"

        record_audit(
            db,
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            action=action,
            resource_type="query",
            resource_id=str(log.id),
            metadata={
                "run_id": run.id,
                "confidence": round(confidence, 4),
                "matched_keywords": decision.matched_keywords,
                "matched_rules": decision.matched_rules,
                "final_action": decision.final_action,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost,
            },
        )

        citations = [
            Citation(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                document_title=c.document_title,
                snippet=c.text[:280],
                score=round(c.score, 4),
                semantic_score=round(c.semantic_score, 4),
                keyword_score=round(c.keyword_score, 4),
                classification=c.classification,
                source_url=c.source_url,
                chunk_index=c.chunk_index,
                start_char=c.start_char,
                end_char=c.end_char,
                page_number=c.page_number,
                section_label=c.section_label,
            )
            for c in ranked
        ]

        response = AskResponse(
            answer=answer,
            confidence=round(confidence, 4),
            citations=citations,
            handoff_recommended=decision.handoff_recommended,
            matched_policy_keywords=decision.matched_keywords,
            matched_policy_rules=decision.matched_rules,
            abstained=abstained,
            query_log_id=log.id,
            run_id=run.id,
            run_status="completed",
            budget_enforced=True,
        )

        add_step(
            db,
            run_id=run.id,
            step_order=5,
            name="verify",
            status="completed",
            metadata={"query_log_id": log.id, "citations": len(citations)},
        )

        finish_run(
            db,
            run=run,
            status="completed",
            response_payload=response.model_dump(),
            error="",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        upsert_idempotent_response(
            db,
            tenant_id=user.tenant_id,
            user_id=user.id,
            endpoint="/api/ask",
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            response=response.model_dump(),
            status_code=200,
            run_id=run.id,
        )

        db.commit()
        return response

    except HTTPException as http_exc:
        finish_run(
            db,
            run=run,
            status="failed",
            response_payload={"detail": http_exc.detail},
            error=str(http_exc.detail),
            input_tokens=estimate_tokens(payload.question),
            output_tokens=0,
        )
        db.commit()
        raise
    except Exception as exc:
        finish_run(
            db,
            run=run,
            status="failed",
            response_payload={"detail": "Internal error"},
            error=str(exc),
            input_tokens=estimate_tokens(payload.question),
            output_tokens=0,
        )
        db.commit()
        raise


@router.get("/ask/history")
def ask_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(QueryLog)
        .filter(QueryLog.tenant_id == user.tenant_id)
        .order_by(QueryLog.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": r.id,
            "question": r.question,
            "confidence": r.confidence,
            "was_answered": r.was_answered,
            "run_id": r.run_id,
            "estimated_input_tokens": r.estimated_input_tokens,
            "estimated_output_tokens": r.estimated_output_tokens,
            "estimated_cost_usd": r.estimated_cost_usd,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/feedback")
def feedback(payload: FeedbackCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models import Feedback

    fb = Feedback(
        tenant_id=user.tenant_id,
        query_log_id=payload.query_log_id,
        user_id=user.id,
        rating=payload.rating,
        reason=payload.reason,
    )
    db.add(fb)

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="ask.feedback",
        resource_type="feedback",
        resource_id="",
        metadata={"rating": payload.rating},
    )

    db.commit()
    db.refresh(fb)
    return {"success": True, "id": fb.id}
