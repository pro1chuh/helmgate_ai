"""
Webhooks API — управление webhook-подписками организации.

Только admin и superadmin своей организации могут управлять webhook'ами.
"""
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, HttpUrl
from typing import Literal
from datetime import datetime
from app.database import get_db
from app.core.auth import get_current_user
from app.models.user import User, UserRole
from app.models.organization import Webhook

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

ALLOWED_EVENTS = {
    "message.created",
    "balance.low",
    "balance.exhausted",
    "chat.created",
}


class WebhookCreate(BaseModel):
    url: str
    events: list[str]
    generate_secret: bool = True  # если True — автоматически генерируем HMAC-секрет


class WebhookOut(BaseModel):
    id: int
    url: str
    events: list[str]
    secret: str | None  # показываем только при создании
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookListItem(BaseModel):
    id: int
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


def _require_admin(current_user: User) -> None:
    if current_user.role not in (UserRole.admin, UserRole.superadmin):
        raise HTTPException(status_code=403, detail="Требуются права администратора")


@router.get("", response_model=list[WebhookListItem])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Список всех webhook'ов организации текущего пользователя."""
    _require_admin(current_user)
    if not current_user.organization_id and current_user.role != UserRole.superadmin:
        return []

    query = select(Webhook)
    if current_user.role != UserRole.superadmin:
        query = query.where(Webhook.organization_id == current_user.organization_id)

    result = await db.execute(query.order_by(Webhook.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=WebhookOut, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Создаёт новый webhook для организации.
    Возвращает секрет — сохраните его, он больше не отображается.
    """
    _require_admin(current_user)
    if not current_user.organization_id:
        raise HTTPException(
            status_code=400,
            detail="Суперадмины должны указать организацию через admin API"
        )

    # Валидируем события
    unknown = set(body.events) - ALLOWED_EVENTS
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Неизвестные события: {', '.join(unknown)}. "
                   f"Допустимые: {', '.join(sorted(ALLOWED_EVENTS))}"
        )

    secret = secrets.token_hex(32) if body.generate_secret else None

    hook = Webhook(
        organization_id=current_user.organization_id,
        url=body.url,
        events=list(set(body.events)),
        secret=secret,
        is_active=True,
    )
    db.add(hook)

    from app.services.audit import audit_log, AuditAction
    await audit_log(
        db=db,
        action=AuditAction.WEBHOOK_CREATE,
        actor_id=current_user.id,
        target_type="webhook",
        details={"url": body.url, "events": body.events},
    )

    await db.commit()
    await db.refresh(hook)
    return hook


@router.patch("/{webhook_id}/toggle", response_model=WebhookListItem)
async def toggle_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Включает/выключает webhook."""
    _require_admin(current_user)
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.organization_id == current_user.organization_id,
        )
    )
    hook = result.scalar_one_or_none()
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    hook.is_active = not hook.is_active
    await db.commit()
    await db.refresh(hook)
    return hook


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удаляет webhook."""
    _require_admin(current_user)
    result = await db.execute(
        select(Webhook).where(
            Webhook.id == webhook_id,
            Webhook.organization_id == current_user.organization_id,
        )
    )
    hook = result.scalar_one_or_none()
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    from app.services.audit import audit_log, AuditAction
    await audit_log(
        db=db,
        action=AuditAction.WEBHOOK_DELETE,
        actor_id=current_user.id,
        target_type="webhook",
        target_id=hook.id,
        details={"url": hook.url},
    )

    await db.delete(hook)
    await db.commit()
