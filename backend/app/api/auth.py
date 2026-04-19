from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import User, UserRole
from app.core.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token,
    revoke_refresh_token, is_token_revoked,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        name=body.name,
        password_hash=hash_password(body.password),
        role=UserRole.user,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    refresh_token, _ = create_refresh_token(user.id)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    refresh_token, _ = create_refresh_token(user.id)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    from jose import JWTError, jwt
    from app.config import get_settings

    settings = get_settings()
    try:
        payload = jwt.decode(body.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload["sub"])
        jti = payload.get("jti")
    except (JWTError, KeyError):
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Проверяем что токен не отозван
    if jti and await is_token_revoked(jti, db):
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Ротация: отзываем старый токен, выдаём новый
    if jti:
        await revoke_refresh_token(jti, user_id, db)

    new_refresh, _ = create_refresh_token(user.id)
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Отзывает refresh-токен. Access-токен истечёт сам по времени."""
    from jose import jwt as jose_jwt, JWTError
    from app.config import get_settings

    settings = get_settings()
    try:
        payload = jose_jwt.decode(body.refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        if jti:
            await revoke_refresh_token(jti, current_user.id, db)
    except JWTError:
        pass  # Невалидный токен — ничего не делаем, всё равно логаут
