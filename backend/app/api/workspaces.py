"""
Мультиворкспейс — разграничение данных между командами.
Каждый воркспейс имеет владельца и список участников.
Чаты внутри воркспейса видны всем его участникам.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqlfunc
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/workspaces", tags=["workspaces"])


# --- Schemas ---

class WorkspaceOut(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: datetime
    member_count: int = 0

    class Config:
        from_attributes = True


class WorkspaceMemberOut(BaseModel):
    user_id: int
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateWorkspaceRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class InviteMemberRequest(BaseModel):
    user_id: int
    role: str = "member"


# --- Helpers ---

async def _get_workspace_or_403(
    workspace_id: int, user_id: int, db: AsyncSession, require_owner: bool = False
) -> Workspace:
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if require_owner:
        if ws.owner_id != user_id:
            raise HTTPException(status_code=403, detail="Only workspace owner can do this")
        return ws

    # Проверяем что пользователь — участник
    member_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    if not member_result.scalar_one_or_none() and ws.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Not a workspace member")

    return ws


# --- Endpoints ---

@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Воркспейсы где пользователь является владельцем или участником."""
    member_ws_ids = (
        select(WorkspaceMember.workspace_id)
        .where(WorkspaceMember.user_id == current_user.id)
        .scalar_subquery()
    )
    result = await db.execute(
        select(Workspace).where(
            (Workspace.owner_id == current_user.id) | (Workspace.id.in_(member_ws_ids))
        ).order_by(Workspace.created_at.desc())
    )
    workspaces = result.scalars().all()

    out = []
    for ws in workspaces:
        count_result = await db.execute(
            select(sqlfunc.count()).select_from(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == ws.id)
        )
        member_count = count_result.scalar() or 0
        out.append(WorkspaceOut(
            id=ws.id, name=ws.name, description=ws.description,
            owner_id=ws.owner_id, created_at=ws.created_at,
            member_count=member_count,
        ))
    return out


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = Workspace(
        name=body.name,
        description=body.description,
        owner_id=current_user.id,
    )
    db.add(ws)
    await db.flush()
    # Владелец автоматически становится участником с ролью owner
    member = WorkspaceMember(
        workspace_id=ws.id, user_id=current_user.id, role="owner"
    )
    db.add(member)
    await db.commit()
    await db.refresh(ws)
    return WorkspaceOut(
        id=ws.id, name=ws.name, description=ws.description,
        owner_id=ws.owner_id, created_at=ws.created_at, member_count=1,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: int,
    body: UpdateWorkspaceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await _get_workspace_or_403(workspace_id, current_user.id, db, require_owner=True)
    if body.name is not None:
        ws.name = body.name
    if body.description is not None:
        ws.description = body.description
    await db.commit()
    await db.refresh(ws)
    count_result = await db.execute(
        select(sqlfunc.count()).select_from(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == ws.id)
    )
    return WorkspaceOut(
        id=ws.id, name=ws.name, description=ws.description,
        owner_id=ws.owner_id, created_at=ws.created_at,
        member_count=count_result.scalar() or 0,
    )


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await _get_workspace_or_403(workspace_id, current_user.id, db, require_owner=True)
    await db.delete(ws)
    await db.commit()


@router.get("/{workspace_id}/members", response_model=list[WorkspaceMemberOut])
async def list_members(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_workspace_or_403(workspace_id, current_user.id, db)
    result = await db.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    )
    return result.scalars().all()


@router.post("/{workspace_id}/members", status_code=201)
async def invite_member(
    workspace_id: int,
    body: InviteMemberRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_workspace_or_403(workspace_id, current_user.id, db, require_owner=True)

    # Проверяем что пользователь существует
    user_result = await db.execute(select(User).where(User.id == body.user_id))
    if not user_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Проверяем что ещё не участник
    existing = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == body.user_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")

    member = WorkspaceMember(
        workspace_id=workspace_id, user_id=body.user_id, role=body.role
    )
    db.add(member)
    await db.commit()
    return {"status": "invited", "user_id": body.user_id, "role": body.role}


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member(
    workspace_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ws = await _get_workspace_or_403(workspace_id, current_user.id, db, require_owner=True)

    if user_id == ws.owner_id:
        raise HTTPException(status_code=400, detail="Cannot remove workspace owner")

    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    await db.delete(member)
    await db.commit()
