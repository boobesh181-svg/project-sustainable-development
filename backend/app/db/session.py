import os
from pathlib import Path

from sqlalchemy import text
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
    """Fail-fast startup DB initialization.

    Requirements:
    - PostgreSQL only (no SQLite).
    - Database must be reachable.
    - Alembic migrations must be applied (DB revision must match Alembic head).
    """

    if async_engine.dialect.name != "postgresql":
        raise RuntimeError(
            f"Invalid database dialect '{async_engine.dialect.name}'. PostgreSQL is required."
        )

    # Verify connection + migrations are at HEAD.
    async with async_engine.begin() as conn:  # type: ignore[func-returns-value]
        await conn.run_sync(lambda _: None)

        try:
            db_revs = list(
                (await conn.execute(text("SELECT version_num FROM alembic_version")))
                .scalars()
                .all()
            )
        except Exception as e:
            raise RuntimeError(
                "Alembic migrations are not applied (missing or unreadable alembic_version table)."
            ) from e
        if not db_revs:
            raise RuntimeError(
                "Alembic migrations are not applied (empty alembic_version table)."
            )

        backend_dir = Path(__file__).resolve().parents[2]
        alembic_ini = backend_dir / "alembic.ini"
        if not alembic_ini.exists():
            raise RuntimeError(f"Missing alembic.ini at expected path: {alembic_ini}")

        try:
            from alembic.config import Config
            from alembic.script import ScriptDirectory
        except Exception as e:
            raise RuntimeError("Alembic is required at runtime to verify migrations.") from e

        cfg = Config(str(alembic_ini))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        if not heads:
            raise RuntimeError("Alembic script has no heads; cannot validate migrations.")

        db_rev_set = {str(r) for r in db_revs}
        head_set = set(heads)

        # If there are multiple Alembic heads, the DB must have exactly those heads applied.
        # If there is a single head, the DB must have exactly one revision row matching it.
        if db_rev_set != head_set:
            raise RuntimeError(
                f"Database schema is not at Alembic HEADS. DB={sorted(db_rev_set)}; heads={sorted(head_set)}"
            )


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
