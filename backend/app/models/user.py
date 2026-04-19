from sqlalchemy import String, Boolean, Enum as SAEnum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
import enum
from app.database import Base
from sqlalchemy import DateTime
from sqlalchemy.sql import func


class UserRole(str, enum.Enum):
    superadmin = "superadmin"  # владельцы Helm (Anatoly + Dmitry)
    admin = "admin"            # администратор компании-клиента
    user = "user"              # обычный сотрудник


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.user)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, default=None)
    # Суточный лимит токенов (0 = без ограничений, NULL = использовать глобальный дефолт)
    daily_token_limit: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    chats: Mapped[list["Chat"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa
    facts: Mapped[list["UserFact"]] = relationship(back_populates="user", cascade="all, delete-orphan")  # noqa
    organization: Mapped["Organization | None"] = relationship(back_populates="members")  # noqa


class UserFact(Base):
    """Долгосрочная память — факты о пользователе."""
    __tablename__ = "user_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="facts")


class RefreshTokenBlacklist(Base):
    """
    Blacklist отозванных refresh-токенов.
    При logout или ротации SECRET_KEY старые jti сюда попадают и больше не принимаются.
    """
    __tablename__ = "refresh_token_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
