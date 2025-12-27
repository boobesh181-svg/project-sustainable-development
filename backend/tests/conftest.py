import asyncio
import os

import pytest


# Ensure the app uses test-safe DB engine settings (see app.db.session).
os.environ.setdefault("APP_TESTING", "1")


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
