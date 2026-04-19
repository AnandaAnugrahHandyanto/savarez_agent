from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import GroupMember, User
from .security import decode_token

bearer = HTTPBearer(auto_error=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    user_id = int(payload.get("uid", 0))
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user


def require_manager_or_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in {"admin", "manager"}:
        raise HTTPException(status_code=403, detail="Manager or admin role required")
    return user


def get_user_group_ids(db: Session, *, tenant_id: int, user_id: int) -> list[int]:
    rows = (
        db.query(GroupMember.group_id)
        .filter(GroupMember.tenant_id == tenant_id, GroupMember.user_id == user_id)
        .all()
    )
    return [int(r[0]) for r in rows]
