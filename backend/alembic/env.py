"""
Alembic environment — async SQLAlchemy (asyncpg).

Запуск миграций:
  # внутри контейнера backend:
  alembic upgrade head

  # локально (с DATABASE_URL в .env):
  alembic -c backend/alembic.ini upgrade head

Автогенерация новой миграции:
  alembic revision --autogenerate -m "describe_change"
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config — даёт доступ к .ini-файлу
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Импортируем все модели, чтобы Base.metadata знал о таблицах
# ---------------------------------------------------------------------------
from app.database import Base  # noqa: E402
from app.models import user, chat, workspace  # noqa: E402, F401

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# DATABASE_URL из настроек (не хардкодим в alembic.ini)
# ---------------------------------------------------------------------------
from app.config import get_settings  # noqa: E402

_settings = get_settings()
config.set_main_option("sqlalchemy.url", _settings.DATABASE_URL)


# ---------------------------------------------------------------------------
# Offline mode (генерация SQL без подключения к БД)
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode (async)
# ---------------------------------------------------------------------------
def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
