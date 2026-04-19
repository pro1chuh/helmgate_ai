"""
Модели для B2B биллинга Helm.

Organization — компания-клиент с балансом.
OrganizationTopUp — история пополнений баланса.
UsageLog — каждый LLM-запрос с реальной стоимостью (для аналитики и списания).
"""
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Text, ForeignKey, Integer, Numeric, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import DateTime
from sqlalchemy.sql import func
from app.database import Base


class OrgStatus(str, enum.Enum):
    active = "active"       # активна, запросы проходят
    suspended = "suspended" # баланс кончился или заморожена вручную
    trial = "trial"         # пробный период


class Organization(Base):
    """Компания-клиент."""
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Основная информация
    company_name: Mapped[str] = mapped_column(String(255), unique=True)
    director_name: Mapped[str] = mapped_column(String(255))   # ФИО директора / контакта
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Лицензия
    employee_count: Mapped[int] = mapped_column(Integer, default=0)  # кол-во сотрудников в договоре

    # Биллинг (рубли, 6 знаков после запятой для точности)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))

    # Статус
    status: Mapped[OrgStatus] = mapped_column(SAEnum(OrgStatus), default=OrgStatus.trial)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    members: Mapped[list["User"]] = relationship(back_populates="organization")  # noqa
    top_ups: Mapped[list["OrganizationTopUp"]] = relationship(back_populates="organization", cascade="all, delete-orphan")
    usage_logs: Mapped[list["UsageLog"]] = relationship(back_populates="organization", cascade="all, delete-orphan")


class OrganizationTopUp(Base):
    """История пополнений баланса организации."""
    __tablename__ = "organization_top_ups"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))   # сумма пополнения в рублях
    comment: Mapped[str | None] = mapped_column(String(500), nullable=True)  # номер счёта, примечание
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="top_ups")


class UsageLog(Base):
    """
    Лог каждого LLM-запроса с реальной стоимостью.
    Используется для:
      - Списания с баланса организации
      - Аналитики в супер-админ панели
      - Детальной истории расходов
    """
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Модель и тип задачи
    model: Mapped[str] = mapped_column(String(100))
    task_type: Mapped[str] = mapped_column(String(50))  # text | code | reasoning | vision | image_gen | asr

    # Токены
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Стоимость в рублях (списывается с баланса)
    cost_rub: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal("0"))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    organization: Mapped["Organization"] = relationship(back_populates="usage_logs")
