"""
Вспомогательные функции для записи в audit log.

Использование:
    from app.services.audit import audit_log

    await audit_log(
        db=db,
        action="org.top_up",
        actor_id=current_user.id,
        target_type="organization",
        target_id=org.id,
        details={"amount": float(amount), "comment": comment},
    )
"""
import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def audit_log(
    db: AsyncSession,
    action: str,
    actor_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    details: dict[str, Any] | None = None,
    ip_address: str | None = None,
    commit: bool = False,
) -> None:
    """
    Добавляет запись в audit_logs.
    commit=False (по умолчанию) — запись добавляется в текущую сессию,
    коммит делается вместе с основной транзакцией.
    commit=True — коммитит самостоятельно (для фоновых задач).
    """
    try:
        from app.models.audit_log import AuditLog
        entry = AuditLog(
            action=action,
            actor_id=actor_id,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        if commit:
            await db.commit()
    except Exception as exc:
        # Ошибка аудита не должна ломать основной запрос
        logger.error(f"audit_log error (action={action}): {exc}")


# Предопределённые константы действий для удобства
class AuditAction:
    # Организации
    ORG_CREATE = "org.create"
    ORG_UPDATE = "org.update"
    ORG_SUSPEND = "org.suspend"
    ORG_ACTIVATE = "org.activate"
    ORG_TOP_UP = "org.top_up"
    ORG_DELETE = "org.delete"

    # Пользователи
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_ROLE_CHANGE = "user.role_change"
    USER_DEACTIVATE = "user.deactivate"
    USER_ACTIVATE = "user.activate"
    USER_DELETE = "user.delete"

    # Чаты
    CHAT_DELETE = "chat.delete"
    CHAT_EXPORT = "chat.export"

    # Webhook
    WEBHOOK_CREATE = "webhook.create"
    WEBHOOK_DELETE = "webhook.delete"
