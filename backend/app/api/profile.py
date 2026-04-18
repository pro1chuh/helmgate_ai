"""
Профиль текущего пользователя.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.core.auth import get_current_user, hash_password, verify_password

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.get("", response_model=ProfileOut)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Возвращает профиль текущего пользователя."""
    return current_user


@router.patch("", response_model=ProfileOut)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновляет имя пользователя."""
    current_user.name = body.name
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Меняет пароль пользователя."""
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Неверный текущий пароль")
    current_user.password_hash = hash_password(body.new_password)
    await db.commit()
