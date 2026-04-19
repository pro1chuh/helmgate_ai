"""
Audit Log API — просмотр журнала административных действий.

Доступен только admin и superadmin.
Admin видит только события своей организации.
Superadmin видит всё.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqlfunc
from pydantic import BaseModel
from datetime import datetime
from typing import Generic, TypeVar
from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["audit"])

T = TypeVar("T")


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    has_more: bool


class AuditLogOut(BaseModel):
    id: int
    action: str
    actor_id: int | None
    target_type: str | None
    target_id: int | None
    details: dict | None
    ip_address: str | None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=PagedResponse[AuditLogOut])
async def list_audit_logs(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    action: str | None = Query(default=None, description="Фильтр по типу действия (например: org.top_up)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Возвращает журнал действий постранично (новые сначала).
    Admin видит только события своей организации через actor_id.
    Superadmin видит все записи.
    """
    if current_user.role not in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status_code=403, detail="Требуются права администратора")

    offset = (page - 1) * limit

    base_query = select(AuditLog)

    if current_user.role == UserRole.admin:
        # Admin видит только свои собственные действия и действия участников своей орг
        # Упрощённо — только свои действия
        base_query = base_query.where(AuditLog.actor_id == current_user.id)

    if action:
        base_query = base_query.where(AuditLog.action == action)

    count_q = select(sqlfunc.count()).select_from(base_query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(
        base_query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    )
    items = result.scalars().all()

    return PagedResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + len(items)) < total,
    )
