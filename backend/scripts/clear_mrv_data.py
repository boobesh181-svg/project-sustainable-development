"""Clear MRV data from database.

Run with: python scripts/clear_mrv_data.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import AsyncSessionLocal
from app.mrv.models import MRVSample, MRVTest, Lab, ChainStep, MRVEventLog
from sqlalchemy import text


async def clear_mrv_data():
    """Clear all MRV data from database."""
    print("Clearing MRV data...")
    
    async with AsyncSessionLocal() as session:
        # Delete in order to respect foreign key constraints
        await session.execute(text("DELETE FROM mrv_event_log"))
        await session.execute(text("DELETE FROM chain_step"))
        await session.execute(text("DELETE FROM mrv_test"))
        await session.execute(text("DELETE FROM mrv_sample"))
        await session.execute(text("DELETE FROM lab"))
        
        await session.commit()
        
        print("MRV data cleared successfully!")


if __name__ == "__main__":
    asyncio.run(clear_mrv_data())
