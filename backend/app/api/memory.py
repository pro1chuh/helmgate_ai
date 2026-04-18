"""
Долгосрочная память пользователя — управление UserFact.
Факты автоматически вставляются в system-prompt при каждом запросе.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_db
from app.models.user import User, UserFact
from app.core.auth import get_current_user

router = APIRouter(prefix="/memory", tags=["memory"])


class FactOut(BaseModel):
    id: int
    key: str
    value: str
    updated_at: datetime

    class Config:
        from_attributes = True


class UpsertFactRequest(BaseModel):
    value: str = Field(..., max_length=1000)


@router.get("", response_model=list[FactOut])
async def list_facts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Возвращает все факты о текущем пользователе."""
    result = await db.execute(
        select(UserFact)
        .where(UserFact.user_id == current_user.id)
        .order_by(UserFact.key)
    )
    return result.scalars().all()


@router.put("/{key}", response_model=FactOut)
async def upsert_fact(
    key: str,
    body: UpsertFactRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт или обновляет факт по ключу."""
    result = await db.execute(
        select(UserFact).where(
            UserFact.user_id == current_user.id,
            UserFact.key == key,
        )
    )
    fact = result.scalar_one_or_none()
    if fact:
        fact.value = body.value
    else:
        fact = UserFact(user_id=current_user.id, key=key, value=body.value)
        db.add(fact)
    await db.commit()
    await db.refresh(fact)
    return fact


@router.delete("/{key}", status_code=204)
async def delete_fact(
    key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Удаляет факт по ключу."""
    result = await db.execute(
        select(UserFact).where(
            UserFact.user_id == current_user.id,
            UserFact.key == key,
        )
    )
    fact = result.scalar_one_or_none()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    await db.delete(fact)
    await db.commit()
