import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings


_poolclass = NullPool if os.getenv("APP_TESTING") == "1" else None

async_engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    echo=False,
    poolclass=_poolclass,
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """Best-effort startup DB initialization.

    This should not prevent the application from starting if the database
    is unavailable; /health will still report DB status separately.
    """
    try:
        async with async_engine.begin() as conn:  # type: ignore[func-returns-value]
            await conn.run_sync(lambda _: None)
    except Exception:
        # Swallow connection errors at startup; app should still boot.
        return


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
