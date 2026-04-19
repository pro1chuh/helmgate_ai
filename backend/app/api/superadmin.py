"""
Супер-админ панель — только для владельцев Helm (роль superadmin).

Управление клиентами (организациями):
  GET    /api/superadmin/organizations           — список всех клиентов
  POST   /api/superadmin/organizations           — добавить клиента
  GET    /api/superadmin/organizations/{id}      — детали + статистика
  PATCH  /api/superadmin/organizations/{id}      — обновить данные
  DELETE /api/superadmin/organizations/{id}      — удалить

Биллинг:
  POST   /api/superadmin/organizations/{id}/topup        — пополнить баланс
  GET    /api/superadmin/organizations/{id}/topups        — история пополнений
  GET    /api/superadmin/organizations/{id}/usage         — история запросов

Пользователи:
  GET    /api/superadmin/organizations/{id}/users         — сотрудники
  PATCH  /api/superadmin/users/{user_id}/organization     — привязать к орг
  POST   /api/superadmin/organizations/{id}/invite        — пригласить пользователя

Дашборд:
  GET    /api/superadmin/stats                   — общая статистика по всем клиентам
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sqlfunc, desc
from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization, OrgStatus, OrganizationTopUp, UsageLog
from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/superadmin", tags=["superadmin"])


# ---------------------------------------------------------------------------
# Guard — только superadmin
# ---------------------------------------------------------------------------

async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Superadmin access required")
    return current_user


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OrgCreate(BaseModel):
    company_name: str
    director_name: str
    email: str | None = None
    phone: str | None = None
    employee_count: int = 0
    notes: str | None = None
    initial_balance: Decimal = Decimal("0")


class OrgUpdate(BaseModel):
    company_name: str | None = None
    director_name: str | None = None
    email: str | None = None
    phone: str | None = None
    employee_count: int | None = None
    notes: str | None = None
    status: OrgStatus | None = None


class OrgOut(BaseModel):
    id: int
    company_name: str
    director_name: str
    email: str | None
    phone: str | None
    employee_count: int
    balance: Decimal
    status: OrgStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrgStats(OrgOut):
    user_count: int
    requests_this_month: int
    cost_this_month: Decimal
    total_spent: Decimal


class TopUpRequest(BaseModel):
    amount: Decimal
    comment: str | None = None


class TopUpOut(BaseModel):
    id: int
    amount: Decimal
    comment: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class UsageOut(BaseModel):
    id: int
    user_id: int
    model: str
    task_type: str
    input_tokens: int
    output_tokens: int
    cost_rub: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class InviteUserRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: UserRole = UserRole.user


# ---------------------------------------------------------------------------
# Дашборд
# ---------------------------------------------------------------------------

@router.get("/stats")
async def superadmin_stats(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Общая статистика по всем клиентам."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_orgs = (await db.execute(sqlfunc.count(Organization.id).select())).scalar() or 0
    active_orgs = (await db.execute(
        select(sqlfunc.count()).select_from(Organization).where(Organization.status == OrgStatus.active)
    )).scalar() or 0
    total_balance = (await db.execute(
        select(sqlfunc.sum(Organization.balance))
    )).scalar() or Decimal("0")
    requests_this_month = (await db.execute(
        select(sqlfunc.count()).select_from(UsageLog).where(UsageLog.created_at >= month_start)
    )).scalar() or 0
    revenue_this_month = (await db.execute(
        select(sqlfunc.sum(OrganizationTopUp.amount)).where(OrganizationTopUp.created_at >= month_start)
    )).scalar() or Decimal("0")
    cost_this_month = (await db.execute(
        select(sqlfunc.sum(UsageLog.cost_rub)).where(UsageLog.created_at >= month_start)
    )).scalar() or Decimal("0")

    return {
        "organizations": {
            "total": total_orgs,
            "active": active_orgs,
            "suspended": total_orgs - active_orgs,
        },
        "balance_total_rub": float(total_balance),
        "this_month": {
            "requests": requests_this_month,
            "revenue_rub": float(revenue_this_month),
            "llm_cost_rub": float(cost_this_month),
            "margin_rub": float(revenue_this_month - cost_this_month),
        },
    }


# ---------------------------------------------------------------------------
# Организации — CRUD
# ---------------------------------------------------------------------------

@router.get("/organizations", response_model=list[OrgOut])
async def list_organizations(
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Organization).order_by(Organization.created_at.desc()))
    return result.scalars().all()


@router.post("/organizations", response_model=OrgOut, status_code=201)
async def create_organization(
    body: OrgCreate,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Organization).where(Organization.company_name == body.company_name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization with this name already exists")

    org = Organization(
        company_name=body.company_name,
        director_name=body.director_name,
        email=body.email,
        phone=body.phone,
        employee_count=body.employee_count,
        notes=body.notes,
        balance=body.initial_balance,
        status=OrgStatus.active if body.initial_balance > 0 else OrgStatus.trial,
    )
    db.add(org)
    await db.flush()  # получаем org.id

    # Если указан начальный баланс — записываем пополнение
    if body.initial_balance > 0:
        db.add(OrganizationTopUp(
            organization_id=org.id,
            amount=body.initial_balance,
            comment="Начальное пополнение",
            created_by=current_user.id,
        ))

    await db.commit()
    await db.refresh(org)
    logger.info(f"Organization created: {org.company_name}", extra={"org_id": org.id})
    return org


@router.get("/organizations/{org_id}", response_model=OrgStats)
async def get_organization(
    org_id: int,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Детали организации + статистика за текущий месяц."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    user_count = (await db.execute(
        select(sqlfunc.count()).select_from(User).where(User.organization_id == org_id)
    )).scalar() or 0
    requests_this_month = (await db.execute(
        select(sqlfunc.count()).select_from(UsageLog).where(
            UsageLog.organization_id == org_id,
            UsageLog.created_at >= month_start,
        )
    )).scalar() or 0
    cost_this_month = (await db.execute(
        select(sqlfunc.sum(UsageLog.cost_rub)).where(
            UsageLog.organization_id == org_id,
            UsageLog.created_at >= month_start,
        )
    )).scalar() or Decimal("0")
    total_spent = (await db.execute(
        select(sqlfunc.sum(UsageLog.cost_rub)).where(UsageLog.organization_id == org_id)
    )).scalar() or Decimal("0")

    return OrgStats(
        **OrgOut.model_validate(org).model_dump(),
        user_count=user_count,
        requests_this_month=requests_this_month,
        cost_this_month=cost_this_month,
        total_spent=total_spent,
    )


@router.patch("/organizations/{org_id}", response_model=OrgOut)
async def update_organization(
    org_id: int,
    body: OrgUpdate,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(org, field, value)

    await db.commit()
    await db.refresh(org)
    return org


@router.delete("/organizations/{org_id}", status_code=204)
async def delete_organization(
    org_id: int,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    await db.delete(org)
    await db.commit()


# ---------------------------------------------------------------------------
# Биллинг — пополнение баланса
# ---------------------------------------------------------------------------

@router.post("/organizations/{org_id}/topup", response_model=OrgOut)
async def top_up_balance(
    org_id: int,
    body: TopUpRequest,
    current_user: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Пополняет баланс организации и активирует её если была suspended."""
    if body.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be positive")

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    org.balance += body.amount
    if org.status == OrgStatus.suspended:
        org.status = OrgStatus.active

    db.add(OrganizationTopUp(
        organization_id=org_id,
        amount=body.amount,
        comment=body.comment,
        created_by=current_user.id,
    ))

    await db.commit()
    await db.refresh(org)
    logger.info(f"Balance topped up: {org.company_name} +{body.amount}₽", extra={"org_id": org_id})
    return org


@router.get("/organizations/{org_id}/topups", response_model=list[TopUpOut])
async def get_top_ups(
    org_id: int,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OrganizationTopUp)
        .where(OrganizationTopUp.organization_id == org_id)
        .order_by(desc(OrganizationTopUp.created_at))
    )
    return result.scalars().all()


@router.get("/organizations/{org_id}/usage", response_model=list[UsageOut])
async def get_usage(
    org_id: int,
    limit: int = 100,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Последние N запросов организации с детализацией."""
    limit = min(limit, 500)
    result = await db.execute(
        select(UsageLog)
        .where(UsageLog.organization_id == org_id)
        .order_by(desc(UsageLog.created_at))
        .limit(limit)
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# Пользователи организации
# ---------------------------------------------------------------------------

@router.get("/organizations/{org_id}/users")
async def get_org_users(
    org_id: int,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.organization_id == org_id).order_by(User.created_at)
    )
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/organizations/{org_id}/invite", status_code=201)
async def invite_user(
    org_id: int,
    body: InviteUserRequest,
    _: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт пользователя и сразу привязывает к организации."""
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    from app.core.auth import hash_password
    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=body.role,
        organization_id=org_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "email": user.email, "name": user.name, "organization_id": org_id}
