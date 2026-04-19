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
    from app.models import user, chat, workspace, organization  # noqa — регистрируем модели

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
            # Биллинг — enum создаётся через DO-блок (PostgreSQL не поддерживает CREATE TYPE IF NOT EXISTS)
            """DO $$ BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'orgstatus') THEN
                    CREATE TYPE orgstatus AS ENUM ('active', 'suspended', 'trial');
                END IF;
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                    CREATE TYPE userrole AS ENUM ('user', 'admin', 'superadmin');
                ELSE
                    BEGIN
                        ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'superadmin';
                    EXCEPTION WHEN others THEN NULL;
                    END;
                END IF;
            END $$""",
            """CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                company_name VARCHAR(255) UNIQUE NOT NULL,
                director_name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                phone VARCHAR(50),
                notes TEXT,
                employee_count INTEGER DEFAULT 0,
                balance NUMERIC(12,6) DEFAULT 0,
                status orgstatus DEFAULT 'trial',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )""",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS organization_id INTEGER REFERENCES organizations(id) ON DELETE SET NULL",
            "ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check",
            """CREATE TABLE IF NOT EXISTS organization_top_ups (
                id SERIAL PRIMARY KEY,
                organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                amount NUMERIC(12,2) NOT NULL,
                comment VARCHAR(500),
                created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            """CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                organization_id INTEGER REFERENCES organizations(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                model VARCHAR(100) NOT NULL,
                task_type VARCHAR(50) NOT NULL,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_rub NUMERIC(12,6) DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW()
            )""",
            "CREATE INDEX IF NOT EXISTS ix_usage_logs_org_id ON usage_logs(organization_id)",
            "CREATE INDEX IF NOT EXISTS ix_usage_logs_created_at ON usage_logs(created_at)",
        ]
        async with engine.begin() as conn:
            for sql in _manual_migrations:
                try:
                    await conn.execute(__import__("sqlalchemy").text(sql))
                except Exception:
                    pass
