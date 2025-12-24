"""Fix migrated demo users that were inserted with an un-verifyable hashed_password.

This is a one-off maintenance script to restore the ability to log in with demo accounts
in dev/demo environments after migrations that inserted placeholder hashes.

Run (Docker):
  docker compose -f backend/docker-compose.yml exec backend python scripts/fix_migrated_demo_passwords.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running as a plain script inside Docker where /app may not be on PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import update

from app.core.security import get_password_hash
from app.db.session import AsyncSessionLocal
from app.models.user import User


DEMO_PASSWORDS: dict[str, str] = {
    # Keep in sync with scripts/run_iso_workflow.ps1 (dev/demo only)
    "admin@example.com": "admin123",  # admin
    "mrv@example.com": "mrv123",  # contractor (creator)
    "verifier@example.com": "verifier123",  # mrv_officer (verifier)
    "approver@example.com": "approver123",  # admin (approver)
}


async def main() -> None:
    async with AsyncSessionLocal() as session:
        for email, password in DEMO_PASSWORDS.items():
            await session.execute(
                update(User)
                .where(User.email == email)
                .values(hashed_password=get_password_hash(password), is_active=True)
            )
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
    print("ok: migrated demo passwords updated")
