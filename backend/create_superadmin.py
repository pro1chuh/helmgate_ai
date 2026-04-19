"""
Скрипт создания superadmin-аккаунта.
Запуск внутри контейнера:
  docker compose exec backend python create_superadmin.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

EMAIL = "pro1chuh@gmail.com"
NAME = "Pro1chuh"
PASSWORD = "12324352"

async def main():
    from app.config import get_settings
    from app.models.user import User, UserRole
    from app.core.auth import hash_password

    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        existing = await db.execute(select(User).where(User.email == EMAIL))
        user = existing.scalar_one_or_none()

        if user:
            user.role = UserRole.superadmin
            user.password_hash = hash_password(PASSWORD)
            user.name = NAME
            await db.commit()
            print(f"✅ Пользователь обновлён до superadmin: {EMAIL}")
        else:
            user = User(
                email=EMAIL,
                name=NAME,
                password_hash=hash_password(PASSWORD),
                role=UserRole.superadmin,
            )
            db.add(user)
            await db.commit()
            print(f"✅ Superadmin создан: {EMAIL}")

    await engine.dispose()

asyncio.run(main())
