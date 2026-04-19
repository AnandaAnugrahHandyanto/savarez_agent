from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..audit_utils import record_audit
from ..database import get_db
from ..deps import require_admin
from ..models import Group, GroupMember, User
from ..schemas import GroupAddMemberByEmailRequest, GroupCreateRequest, GroupOut

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
def list_groups(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.query(Group).filter(Group.tenant_id == admin.tenant_id).order_by(Group.created_at.desc()).all()
    out = []
    for g in rows:
        member_count = (
            db.query(func.count(GroupMember.id))
            .filter(GroupMember.tenant_id == admin.tenant_id, GroupMember.group_id == g.id)
            .scalar()
            or 0
        )
        out.append(GroupOut(id=g.id, name=g.name, description=g.description, member_count=member_count, created_at=g.created_at))
    return out


@router.post("", response_model=GroupOut)
def create_group(payload: GroupCreateRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    exists = (
        db.query(Group)
        .filter(Group.tenant_id == admin.tenant_id, Group.name == payload.name.strip())
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Group name already exists")

    g = Group(tenant_id=admin.tenant_id, name=payload.name.strip(), description=payload.description.strip())
    db.add(g)
    db.flush()

    record_audit(
        db,
        tenant_id=admin.tenant_id,
        actor_user_id=admin.id,
        action="groups.create",
        resource_type="group",
        resource_id=str(g.id),
        metadata={"name": g.name},
    )

    db.commit()
    db.refresh(g)
    return GroupOut(id=g.id, name=g.name, description=g.description, member_count=0, created_at=g.created_at)


@router.post("/{group_id}/members/by-email")
def add_member_by_email(
    group_id: int,
    payload: GroupAddMemberByEmailRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    g = db.query(Group).filter(Group.id == group_id, Group.tenant_id == admin.tenant_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Group not found")

    user = db.query(User).filter(User.tenant_id == admin.tenant_id, User.email == payload.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in tenant")

    exists = (
        db.query(GroupMember)
        .filter(GroupMember.tenant_id == admin.tenant_id, GroupMember.group_id == g.id, GroupMember.user_id == user.id)
        .first()
    )
    if exists:
        return {"success": True, "message": "Already a member"}

    db.add(GroupMember(tenant_id=admin.tenant_id, group_id=g.id, user_id=user.id))
    record_audit(
        db,
        tenant_id=admin.tenant_id,
        actor_user_id=admin.id,
        action="groups.add_member",
        resource_type="group",
        resource_id=str(g.id),
        metadata={"user_id": user.id, "email": user.email},
    )
    db.commit()
    return {"success": True}


@router.delete("/{group_id}/members/{user_id}")
def remove_member(group_id: int, user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    row = (
        db.query(GroupMember)
        .filter(GroupMember.tenant_id == admin.tenant_id, GroupMember.group_id == group_id, GroupMember.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(row)
    record_audit(
        db,
        tenant_id=admin.tenant_id,
        actor_user_id=admin.id,
        action="groups.remove_member",
        resource_type="group",
        resource_id=str(group_id),
        metadata={"user_id": user_id},
    )
    db.commit()
    return {"success": True}
