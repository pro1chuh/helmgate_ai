from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

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
    from app.models import user, chat  # noqa — ensure models are registered
    from sqlalchemy.exc import ProgrammingError, IntegrityError
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except (ProgrammingError, IntegrityError):
        # Enum types already exist (e.g. on restart with multiple workers) — safe to ignore
        pass
