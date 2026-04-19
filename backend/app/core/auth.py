import uuid
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.database import get_db

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """Возвращает (token, jti) — jti нужен для blacklist при logout."""
    jti = uuid.uuid4().hex
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "refresh", "jti": jti},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return token, jti


async def revoke_refresh_token(jti: str, user_id: int, db: AsyncSession) -> None:
    """Добавляет jti в blacklist. Вызывается при logout и ротации токена."""
    from app.models.user import RefreshTokenBlacklist
    db.add(RefreshTokenBlacklist(jti=jti, user_id=user_id))
    await db.commit()


async def is_token_revoked(jti: str, db: AsyncSession) -> bool:
    from app.models.user import RefreshTokenBlacklist
    result = await db.execute(
        select(RefreshTokenBlacklist).where(RefreshTokenBlacklist.jti == jti)
    )
    return result.scalar_one_or_none() is not None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    from app.models.user import User

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id), User.is_active == True))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user
