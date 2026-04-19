"""
Audit log — журнал административных действий.

Логирует:
  - Создание/изменение/удаление организаций
  - Пополнения баланса
  - Изменение ролей пользователей
  - Приостановку/восстановление аккаунтов

Записи нельзя редактировать или удалять через API — только читать.
"""
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from sqlalchemy.sql import func
from app.database import Base


class AuditLog(Base):
    """
    Одна запись в журнале действий.

    action — строка вида "org.create", "org.top_up", "user.role_change", ...
    actor_id — ID пользователя который выполнил действие
    target_type — тип объекта действия: "organization" | "user" | "chat"
    target_id — ID объекта
    details — произвольный JSON с деталями (старое/новое значение, сумма, и т.д.)
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # IPv4/IPv6
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
