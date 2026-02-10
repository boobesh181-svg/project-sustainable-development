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
BACKEND_ROOT = CURRENT_FILE.parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api import deps
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.emission_factor import EmissionFactor
from app.models.activity_record import ActivityRecord
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


def _make_user(*, user_id: uuid.UUID, email: str, role_name: RoleName):
    class DummyUser:
        def __init__(self):
            self.id = user_id
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


@pytest.mark.asyncio
async def test_mrv_verification_requires_ack_or_deemed_observed():
    # Arrange: create contractor + MRV officer + project + emission factor.
    async with AsyncSessionLocal() as session:
        await session.begin()

        contractor_role = await _get_or_create_role(session, RoleName.CONTRACTOR)
        officer_role = await _get_or_create_role(session, RoleName.MRV_OFFICER)

        contractor = await _create_user(session, role=contractor_role, email_prefix="contractor")
        officer = await _create_user(session, role=officer_role, email_prefix="officer")

        project = Project(
            name=f"AckGate Project {uuid.uuid4()}",
            status=ProjectStatus.ACTIVE,
            lat=1.0,
            lon=1.0,
            budget_usd=1000.0,
            created_by=contractor.id,
        )
        session.add(project)
        await session.flush()

        ef = EmissionFactor(
            material_code=f"CEM_TEST_{uuid.uuid4().hex[:8]}",
            material_name="Cement Test",
            version=1,
            co2e_per_unit=2.0,
            unit="kg",
            source_type="National",
            jurisdiction="GLOBAL",
            methodology_reference="test",
            valid_from=datetime.now(timezone.utc),
            valid_to=None,
            factor_hash="",
            is_active=True,
            created_by="test",
            created_by_user_id=contractor.id,
        )
        ef.factor_hash = ef.generate_hash()
        session.add(ef)
        await session.flush()

        await session.commit()

    client = TestClient(app)

    try:
        # Contractor creates report (with a deliberately wrong total_co2e).
        app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
            user_id=contractor.id,
            email=contractor.email,
            role_name=RoleName.CONTRACTOR,
        )

        res = client.post(
            "/api/v1/mrv-approval/reports",
            json={
                "project_id": str(project.id),
                "reporting_period": "2026-Q1",
                "sample_desc": "test",
                "parameter": "qty",
                "value": "10",
                "total_co2e": 999.0,
                "emission_factor_id": str(ef.id),
                "certificate_path": None,
            },
        )
        assert res.status_code == 201, res.text
        report = res.json()
        report_id = report["id"]

        # Ensure a notification exists for *this* officer (default routing may choose a different MRV officer
        # if the database already contains seeded MRV officers).
        async with AsyncSessionLocal() as session:
            activity = (
                await session.execute(
                    select(ActivityRecord)
                    .where(ActivityRecord.mrv_report_id == uuid.UUID(report_id))
                    .limit(1)
                )
            ).scalar_one_or_none()
            assert activity is not None

        res = client.post(
            f"/api/v1/events/{activity.id}/notify",
            json={
                "notified_user_id": str(officer.id),
                "delivery_channel": "in_app",
                "response_window_hours": 48,
            },
        )
        assert res.status_code == 201, res.text

        # Server should derive total_co2e from snapshots when available (10 * 2 = 20).
        assert abs(float(report["total_co2e"]) - 20.0) < 1e-6

        # Contractor submits.
        res = client.post(
            f"/api/v1/mrv-approval/reports/{report_id}/advance",
            json={"next_status": "SUBMITTED"},
        )
        assert res.status_code == 200, res.text

        # Officer attempts verify without acknowledging → blocked.
        app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
            user_id=officer.id,
            email=officer.email,
            role_name=RoleName.MRV_OFFICER,
        )

        res = client.post(
            f"/api/v1/mrv-approval/reports/{report_id}/advance",
            json={"next_status": "VERIFIED"},
        )
        assert res.status_code == 409, res.text

        # Officer acknowledges the notification.
        pending = client.get("/api/v1/notifications/pending")
        assert pending.status_code == 200, pending.text
        pending_items = pending.json()
        assert isinstance(pending_items, list)
        assert len(pending_items) >= 1

        # Find notification tied to this report's MRV_REPORT_CREATED activity.
        target = next((n for n in pending_items if n.get("activity_id") == str(activity.id)), None)
        assert target is not None

        resp = client.post(
            f"/api/v1/notifications/{target['id']}/respond",
            json={"response_type": "acknowledge", "response_comment": None},
        )
        assert resp.status_code == 201, resp.text

        # Now verification should succeed.
        res = client.post(
            f"/api/v1/mrv-approval/reports/{report_id}/advance",
            json={"next_status": "VERIFIED"},
        )
        assert res.status_code == 200, res.text
        assert res.json()["status"] == "VERIFIED"

    finally:
        app.dependency_overrides = {}
