"""
Панель администратора — только для role=admin.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.database import get_db
from app.models.user import User, UserRole
from app.models.chat import Chat, Message, Document
from app.core.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Dependency: проверка роли ---

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Требуются права администратора")
    return current_user


# --- Schemas ---

class UserAdminOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PatchUserRequest(BaseModel):
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None


class StatsOut(BaseModel):
    users_total: int
    users_active: int
    chats_total: int
    messages_total: int
    documents_total: int


# --- Endpoints ---

@router.get("/users", response_model=list[UserAdminOut])
async def list_users(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Список всех пользователей."""
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserAdminOut)
async def patch_user(
    user_id: int,
    body: PatchUserRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Изменяет статус или роль пользователя."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить собственную учётную запись")
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.role is not None:
        user.role = body.role
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Сводная статистика по системе."""
    users_total = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    users_active = (await db.execute(
        select(func.count()).select_from(User).where(User.is_active == True)
    )).scalar() or 0
    chats_total = (await db.execute(select(func.count()).select_from(Chat))).scalar() or 0
    messages_total = (await db.execute(select(func.count()).select_from(Message))).scalar() or 0
    documents_total = (await db.execute(select(func.count()).select_from(Document))).scalar() or 0

    return StatsOut(
        users_total=users_total,
        users_active=users_active,
        chats_total=chats_total,
        messages_total=messages_total,
        documents_total=documents_total,
    )
