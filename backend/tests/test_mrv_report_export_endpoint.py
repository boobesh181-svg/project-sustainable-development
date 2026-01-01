import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

# Ensure backend root is on sys.path (matches existing test pattern)
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api import deps
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.mrv_report import MRVReport, MRVStatus
from app.models.project import Project, ProjectStatus
from app.models.role import Role, RoleName
from app.models.user import User


def _db_reachable() -> bool:
    try:
        parsed = urlparse(settings.DATABASE_URL)
        if not parsed.hostname or not parsed.port:
            return False
        with socket.create_connection((parsed.hostname, parsed.port), timeout=0.5):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="Postgres is not reachable at settings.DATABASE_URL",
)


def _make_user(email: str, role_name: RoleName):
    class DummyUser:
        def __init__(self):
            self.id = "00000000-0000-0000-0000-000000000000"
            self.email = email
            self.full_name = "Test User"
            self.is_active = True

            r = Role()
            r.id = 1
            r.name = role_name
            self.role = r

            self.created_at = datetime(2025, 12, 25, 0, 0, 0, tzinfo=timezone.utc)

    return DummyUser()


async def _get_or_create_role(session, name: RoleName) -> Role:
    res = await session.execute(select(Role).where(Role.name == name))
    role = res.scalar_one_or_none()
    if role is None:
        role = Role(name=name)
        session.add(role)
        await session.flush()
    return role


async def _create_user(session, *, role: Role, email_prefix: str) -> User:
    user = User(
        email=f"{email_prefix}+{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        full_name=email_prefix,
        is_active=True,
        role_id=role.id,
    )
    session.add(user)
    await session.flush()
    return user


async def _create_report(session, *, status: MRVStatus) -> MRVReport:
    admin_role = await _get_or_create_role(session, RoleName.ADMIN)
    officer_role = await _get_or_create_role(session, RoleName.MRV_OFFICER)
    contractor_role = await _get_or_create_role(session, RoleName.CONTRACTOR)

    creator = await _create_user(session, role=contractor_role, email_prefix="creator")
    verifier = await _create_user(session, role=officer_role, email_prefix="verifier")
    approver = await _create_user(session, role=admin_role, email_prefix="approver")

    project = Project(
        name=f"Test Project {uuid.uuid4()}",
        status=ProjectStatus.ACTIVE,
        lat=1.0,
        lon=1.0,
        budget_usd=1000.0,
        created_by=creator.id,
    )
    session.add(project)
    await session.flush()

    report = MRVReport(
        project_id=project.id,
        reporting_period="2025-Q1",
        sample_desc="Sample",
        parameter="cement",
        value="100",
        total_co2e=1.234567,
        created_by=creator.id,
        status=status,
    )
    if status in (MRVStatus.VERIFIED, MRVStatus.APPROVED, MRVStatus.LOCKED):
        report.verified_by = verifier.id
    if status in (MRVStatus.APPROVED, MRVStatus.LOCKED):
        report.approved_by = approver.id
    session.add(report)
    await session.flush()
    return report


@pytest.mark.asyncio
async def test_mrv_report_export_blocks_unapproved_reports():
    async with AsyncSessionLocal() as session:
        await session.begin()
        report = await _create_report(session, status=MRVStatus.DRAFT)
        await session.commit()

    client = TestClient(app)
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "admin@example.com", RoleName.ADMIN
    )

    res = client.get(f"/api/v1/mrv/export/{report.id}")
    assert res.status_code == 400

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_mrv_report_export_is_deterministic_for_same_input():
    async with AsyncSessionLocal() as session:
        await session.begin()
        report = await _create_report(session, status=MRVStatus.APPROVED)
        await session.commit()

    client = TestClient(app)
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "admin@example.com", RoleName.ADMIN
    )

    res1 = client.get(f"/api/v1/mrv/export/{report.id}")
    assert res1.status_code == 200

    res2 = client.get(f"/api/v1/mrv/export/{report.id}")
    assert res2.status_code == 200

    assert res1.content == res2.content

    app.dependency_overrides = {}
