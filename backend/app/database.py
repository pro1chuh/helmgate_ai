import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    Применяет Alembic-миграции при старте (alembic upgrade head).
    Если Alembic не настроен или что-то пошло не так — fallback на create_all,
    чтобы приложение всегда запустилось.
    """
    from app.models import user, chat, workspace  # noqa — регистрируем модели

    try:
        import asyncio
        from alembic.config import Config
        from alembic import command

        def _run_upgrade():
            alembic_cfg = Config("/app/alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            command.upgrade(alembic_cfg, "head")

        await asyncio.to_thread(_run_upgrade)
        logger.info("Alembic migrations applied")

    except Exception as exc:
        logger.warning(
            "Alembic upgrade failed, falling back to create_all",
            extra={"error": str(exc)},
        )
        # Fallback — гарантирует запуск даже без alembic.ini в контейнере
        from sqlalchemy.exc import ProgrammingError, IntegrityError
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except (ProgrammingError, IntegrityError):
            pass

        # Ручные миграции для обратной совместимости (IF NOT EXISTS — безопасно)
        _manual_migrations = [
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS system_prompt TEXT",
            "ALTER TABLE chats ADD COLUMN IF NOT EXISTS workspace_id INTEGER REFERENCES workspaces(id) ON DELETE SET NULL",
            """CREATE TABLE IF NOT EXISTS refresh_token_blacklist (
                id SERIAL PRIMARY KEY,
                jti VARCHAR(64) UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                revoked_at TIMESTAMP DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS ix_refresh_token_blacklist_jti ON refresh_token_blacklist(jti)",
        ]
        async with engine.begin() as conn:
            for sql in _manual_migrations:
                try:
                    await conn.execute(__import__("sqlalchemy").text(sql))
                except Exception:
                    pass
