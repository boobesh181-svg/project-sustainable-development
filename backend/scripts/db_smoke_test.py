import asyncio
import os

import asyncpg
from dotenv import load_dotenv


def _dsn() -> str:
    load_dotenv()  # loads backend/.env when running from backend/
    dsn = os.environ["DATABASE_URL"]
    # asyncpg expects postgresql://
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


async def main() -> None:
    dsn = _dsn()
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=3)
        v = await conn.fetchval("select 1")
        await conn.close()
        print("DB OK", v)
    except Exception as e:
        print("DB FAIL", type(e).__name__, e)
        raise


if __name__ == "__main__":
    asyncio.run(main())
