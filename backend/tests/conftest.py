import asyncio
import os
from pathlib import Path

import pytest


# Ensure the app uses test-safe DB engine settings (see app.db.session).
os.environ.setdefault("APP_TESTING", "1")


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations():
    """Apply Alembic migrations for test runs.

    Tests rely on the database schema being at HEAD.
    """

    try:
        from alembic import command
        from alembic.config import Config
    except Exception:
        # If Alembic isn't installed, tests that require DB schema will fail anyway.
        return

    backend_dir = Path(__file__).resolve().parents[1]
    alembic_ini = backend_dir / "alembic.ini"
    cfg = Config(str(alembic_ini))
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the whole test session.

    This avoids asyncpg/SQLAlchemy pool issues on Windows where connections
    can become bound to a closed per-test loop.
    """

    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        try:
            from app.db.session import async_engine

            loop.run_until_complete(async_engine.dispose())
        finally:
            loop.close()
