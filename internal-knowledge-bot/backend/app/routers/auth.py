from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import Tenant, TenantPolicy, User
from ..policy import get_policy_pack, normalize_keywords
from ..schemas import CreateUserRequest, LoginRequest, RegisterRequest, TokenResponse, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def ensure_tenant_policy(db: Session, tenant_id: int) -> TenantPolicy:
    policy = db.query(TenantPolicy).filter(TenantPolicy.tenant_id == tenant_id).first()
    if policy:
        return policy

    pack = get_policy_pack("balanced")
    policy = TenantPolicy(
        tenant_id=tenant_id,
        policy_pack="balanced",
        min_confidence=float(pack["min_confidence"]),
        max_citations=int(pack["max_citations"]),
        daily_query_budget=int(pack["daily_query_budget"]),
        daily_run_budget=int(pack["daily_run_budget"]),
        daily_cost_budget_usd=float(pack["daily_cost_budget_usd"]),
        max_top_k=int(pack["max_top_k"]),
        max_question_chars=int(pack["max_question_chars"]),
        force_handoff_keywords_json=__import__("json").dumps(normalize_keywords(pack["force_handoff_keywords"])),
    )
    db.add(policy)
    db.flush()
    return policy


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already registered")

    tenant = Tenant(company_name=payload.company_name.strip())
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower(),
        name=payload.name.strip(),
        role="admin",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    ensure_tenant_policy(db, tenant.id)
    record_audit(
        db,
        tenant_id=tenant.id,
        actor_user_id=user.id,
        action="auth.register",
        resource_type="tenant",
        resource_id=str(tenant.id),
        metadata={"email": user.email},
    )

    db.commit()
    db.refresh(user)

    token = create_access_token(user.email, extra={"uid": user.id, "tid": user.tenant_id, "role": user.role})
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower(), User.is_active.is_(True)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    record_audit(
        db,
        tenant_id=user.tenant_id,
        actor_user_id=user.id,
        action="auth.login",
        resource_type="user",
        resource_id=str(user.id),
        metadata={},
    )
    db.commit()

    token = create_access_token(user.email, extra={"uid": user.id, "tid": user.tenant_id, "role": user.role})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, tenant_id=user.tenant_id, email=user.email, name=user.name, role=user.role)


@router.post("/users", response_model=UserOut)
def create_user(payload: CreateUserRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(User).filter(User.email == payload.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already exists")

    user = User(
        tenant_id=admin.tenant_id,
        email=payload.email.lower(),
        name=payload.name.strip(),
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    record_audit(
        db,
        tenant_id=admin.tenant_id,
        actor_user_id=admin.id,
        action="auth.create_user",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"role": payload.role, "email": user.email},
    )
    db.commit()
    db.refresh(user)

    return UserOut(id=user.id, tenant_id=user.tenant_id, email=user.email, name=user.name, role=user.role)
