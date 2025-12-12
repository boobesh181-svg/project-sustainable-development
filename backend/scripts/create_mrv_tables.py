"""Quick script to create MRV tables for demo purposes.

Run with: python scripts/create_mrv_tables.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import async_engine
from app.db.base import Base
from app.mrv.models import MRVSample, MRVTest, Lab, ChainStep, MRVEventLog


async def create_mrv_tables() -> None:
    """Create MRV tables directly using SQLAlchemy."""
    print("Creating MRV tables...")
    
    async with async_engine.begin() as conn:
        # Create all MRV tables
        await conn.run_sync(Base.metadata.create_all, tables=[
            MRVSample.__table__,
            Lab.__table__,
            MRVTest.__table__,
            ChainStep.__table__,
            MRVEventLog.__table__,
        ])
    
    print("MRV tables created successfully!")


if __name__ == "__main__":
    asyncio.run(create_mrv_tables())
