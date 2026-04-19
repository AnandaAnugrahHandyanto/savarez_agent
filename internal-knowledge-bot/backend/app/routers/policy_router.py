import json
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..database import get_db
from ..deps import require_admin
from ..models import TenantPolicy, User
from ..policy import evaluate_handoff_decision, get_policy_pack, normalize_keywords
from ..schemas import (
    PolicyValidationRequest,
    PolicyValidationResponse,
    TenantPolicyOut,
    TenantPolicyRule,
    TenantPolicyUpdate,
)

router = APIRouter(prefix="/api/policy", tags=["policy"])


def _get_or_create(db: Session, tenant_id: int) -> TenantPolicy:
    p = db.query(TenantPolicy).filter(TenantPolicy.tenant_id == tenant_id).first()
    if p:
        return p

    pack = get_policy_pack("balanced")
    p = TenantPolicy(
        tenant_id=tenant_id,
        policy_pack="balanced",
        min_confidence=float(pack["min_confidence"]),
        max_citations=int(pack["max_citations"]),
        daily_query_budget=int(pack["daily_query_budget"]),
        daily_run_budget=int(pack["daily_run_budget"]),
        daily_cost_budget_usd=float(pack["daily_cost_budget_usd"]),
        max_top_k=int(pack["max_top_k"]),
        max_question_chars=int(pack["max_question_chars"]),
        force_handoff_keywords_json=json.dumps(normalize_keywords(pack["force_handoff_keywords"])),
    )
    db.add(p)
    db.flush()
    return p


def _load_rules(p: TenantPolicy) -> list[dict]:
    try:
        rules = json.loads(p.policy_rules_json)
        if isinstance(rules, list):
            return rules
    except Exception:
        pass
    return []


def _to_out(p: TenantPolicy) -> TenantPolicyOut:
    try:
        kws = json.loads(p.force_handoff_keywords_json)
    except Exception:
        kws = []
    rules_out: list[TenantPolicyRule] = []
    for r in _load_rules(p):
        try:
            rules_out.append(TenantPolicyRule(**r))
        except Exception:
            continue
    return TenantPolicyOut(
        min_confidence=p.min_confidence,
        force_handoff_keywords=kws,
        pii_redaction_enabled=p.pii_redaction_enabled,
        max_citations=p.max_citations,
        rules=rules_out,
        policy_pack=p.policy_pack,
        daily_query_budget=p.daily_query_budget,
        daily_run_budget=p.daily_run_budget,
        daily_cost_budget_usd=round(float(p.daily_cost_budget_usd), 8),
        max_top_k=p.max_top_k,
        max_question_chars=p.max_question_chars,
    )


def _apply_pack(p: TenantPolicy, pack_name: str) -> None:
    pack = get_policy_pack(pack_name)
    p.policy_pack = pack_name
    p.min_confidence = float(pack["min_confidence"])
    p.max_citations = int(pack["max_citations"])
    p.daily_query_budget = int(pack["daily_query_budget"])
    p.daily_run_budget = int(pack["daily_run_budget"])
    p.daily_cost_budget_usd = float(pack["daily_cost_budget_usd"])
    p.max_top_k = int(pack["max_top_k"])
    p.max_question_chars = int(pack["max_question_chars"])
    p.force_handoff_keywords_json = json.dumps(normalize_keywords(pack["force_handoff_keywords"]))


@router.get("", response_model=TenantPolicyOut)
def get_policy(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return _to_out(_get_or_create(db, admin.tenant_id))


@router.put("", response_model=TenantPolicyOut)
def update_policy(payload: TenantPolicyUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = _get_or_create(db, admin.tenant_id)

    if payload.policy_pack is not None:
        _apply_pack(p, payload.policy_pack)

    if payload.min_confidence is not None:
        p.min_confidence = max(0.0, min(1.0, float(payload.min_confidence)))
    if payload.force_handoff_keywords is not None:
        p.force_handoff_keywords_json = json.dumps(normalize_keywords(payload.force_handoff_keywords))
    if payload.pii_redaction_enabled is not None:
        p.pii_redaction_enabled = bool(payload.pii_redaction_enabled)
    if payload.max_citations is not None:
        p.max_citations = max(1, min(10, int(payload.max_citations)))
    if payload.rules is not None:
        p.policy_rules_json = json.dumps([r.model_dump() for r in payload.rules])

    if payload.daily_query_budget is not None:
        p.daily_query_budget = int(payload.daily_query_budget)
    if payload.daily_run_budget is not None:
        p.daily_run_budget = int(payload.daily_run_budget)
    if payload.daily_cost_budget_usd is not None:
        p.daily_cost_budget_usd = float(payload.daily_cost_budget_usd)
    if payload.max_top_k is not None:
        p.max_top_k = int(payload.max_top_k)
    if payload.max_question_chars is not None:
        p.max_question_chars = int(payload.max_question_chars)

    p.updated_at = datetime.utcnow()
    db.add(p)

    record_audit(
        db,
        tenant_id=admin.tenant_id,
        actor_user_id=admin.id,
        action="policy.update",
        resource_type="tenant_policy",
        resource_id=str(p.id),
        metadata={
            "policy_pack": p.policy_pack,
            "daily_query_budget": p.daily_query_budget,
            "daily_run_budget": p.daily_run_budget,
            "daily_cost_budget_usd": p.daily_cost_budget_usd,
            "max_top_k": p.max_top_k,
            "max_question_chars": p.max_question_chars,
        },
    )

    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.post("/validate", response_model=PolicyValidationResponse)
def validate_policy(payload: PolicyValidationRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    p = _get_or_create(db, admin.tenant_id)

    try:
        force_keywords = json.loads(p.force_handoff_keywords_json)
        if not isinstance(force_keywords, list):
            force_keywords = []
    except Exception:
        force_keywords = []

    decision = evaluate_handoff_decision(
        question=payload.question,
        confidence=payload.confidence,
        min_confidence=p.min_confidence,
        force_keywords=force_keywords,
        rules=_load_rules(p),
        answer="",
        classification=payload.classification,
        role=payload.role,
    )

    return PolicyValidationResponse(
        handoff_recommended=decision.handoff_recommended,
        matched_keywords=decision.matched_keywords,
        matched_rules=decision.matched_rules,
        final_action=decision.final_action,
    )
