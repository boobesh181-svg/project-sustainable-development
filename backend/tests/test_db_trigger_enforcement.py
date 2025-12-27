import socket
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

# Ensure backend root is on sys.path (matches existing test pattern)
CURRENT_FILE = Path(__file__).resolve()
BACKEND_ROOT = CURRENT_FILE.parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.emission_factor import EmissionFactor
from app.models.evidence import Evidence
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


async def _create_approved_report(session) -> MRVReport:
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
        status=MRVStatus.DRAFT,
    )
    session.add(report)
    await session.flush()

    report.status = MRVStatus.SUBMITTED
    await session.flush()

    report.status = MRVStatus.VERIFIED
    report.verified_by = verifier.id
    await session.flush()

    report.status = MRVStatus.APPROVED
    report.approved_by = approver.id
    await session.flush()

    return report


@pytest.mark.asyncio
async def test_mrv_report_db_blocks_edits_after_approved():
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            report = await _create_approved_report(session)

            # Any update from APPROVED except APPROVED->LOCKED should be blocked
            report.total_co2e = 9.999999
            with pytest.raises(DBAPIError):
                await session.flush()
        finally:
            await session.rollback()


@pytest.mark.asyncio
async def test_mrv_report_db_allows_only_approved_to_locked_transition():
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            report = await _create_approved_report(session)

            report.status = MRVStatus.LOCKED
            await session.flush()  # should succeed

            # Once LOCKED, any update is blocked
            report.sample_desc = "changed"
            with pytest.raises(DBAPIError):
                await session.flush()
        finally:
            await session.rollback()


@pytest.mark.asyncio
async def test_emission_factor_db_is_append_only_and_immutable():
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            now = datetime.now(timezone.utc)
            ef = EmissionFactor(
                material_code=f"TEST_EF_{uuid.uuid4().hex[:8]}",
                material_name="Test EF",
                version=1,
                co2e_per_unit=1.000001,
                unit="kg",
                valid_from=now,
                valid_to=None,
                created_by="test",
                factor_hash="",
                is_active=False,
            )
            ef.factor_hash = ef.generate_hash()
            session.add(ef)
            await session.flush()

            # Updates to factor data are blocked (must create new version)
            ef.co2e_per_unit = 2.0
            with pytest.raises(DBAPIError):
                await session.flush()
        finally:
            await session.rollback()


@pytest.mark.asyncio
async def test_evidence_db_becomes_immutable_after_verification():
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            admin_role = await _get_or_create_role(session, RoleName.ADMIN)
            admin = await _create_user(session, role=admin_role, email_prefix="admin")

            ev = Evidence(
                upload_type="mrv_certificate",
                storage_path="uploads/material_evidence/test.pdf",
                sha256="0" * 64,
                size_bytes=123,
                content_type="application/pdf",
                original_filename="test.pdf",
                created_by=admin.id,
            )
            session.add(ev)
            await session.flush()

            # Before verification: core fields are immutable already
            ev.storage_path = "uploads/material_evidence/changed.pdf"
            with pytest.raises(DBAPIError):
                await session.flush()

        finally:
            await session.rollback()

    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            admin_role = await _get_or_create_role(session, RoleName.ADMIN)
            admin = await _create_user(session, role=admin_role, email_prefix="admin")

            ev = Evidence(
                upload_type="mrv_certificate",
                storage_path="uploads/material_evidence/test.pdf",
                sha256="1" * 64,
                size_bytes=123,
                content_type="application/pdf",
                original_filename="test.pdf",
                created_by=admin.id,
            )
            session.add(ev)
            await session.flush()

            ev.verified_at = datetime.now(timezone.utc)
            ev.verified_by = admin.id
            ev.verification_notes = "ok"
            await session.flush()  # allowed (verification fields)

            # After verification: ANY update is blocked
            ev.verification_notes = "changed"
            with pytest.raises(DBAPIError):
                await session.flush()

        finally:
            await session.rollback()

    # Activation/deactivation allowed only via is_active flip
    async with AsyncSessionLocal() as session:
        await session.begin()
        try:
            now = datetime.now(timezone.utc)
            ef = EmissionFactor(
                material_code=f"TEST_EF_{uuid.uuid4().hex[:8]}",
                material_name="Test EF",
                version=1,
                co2e_per_unit=1.5,
                unit="kg",
                valid_from=now,
                valid_to=None,
                created_by="test",
                factor_hash="",
                is_active=False,
            )
            ef.factor_hash = ef.generate_hash()
            session.add(ef)
            await session.flush()

            ef.is_active = True
            await session.flush()  # should succeed

            # Deleting is always blocked
            await session.delete(ef)
            with pytest.raises(DBAPIError):
                await session.flush()
        finally:
            await session.rollback()
