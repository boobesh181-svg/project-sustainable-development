import socket
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
from app.models.emission_factor import EmissionFactor
from app.models.material_token import MaterialToken
from app.models.organization import Organization
from app.models.organization_relationship import OrganizationRelationship, OrganizationRoleType
from app.models.project import Project, ProjectStatus
from app.models.reporting_context import ConsolidationMethod, ReportingContext, ReportingPurpose
from app.models.methodology_version import MethodologyVersion
from app.models.role import Role, RoleName
from app.models.supplier import Supplier
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
async def test_same_events_different_methodology_yields_different_totals():
    # Arrange: two methodology versions with different emission factors for the same material code.
    async with AsyncSessionLocal() as session:
        await session.begin()

        pm_role = await _get_or_create_role(session, RoleName.PROJECT_MANAGER)
        pm = await _create_user(session, role=pm_role, email_prefix="pm")

        org = Organization(name=f"Reporting Entity {uuid.uuid4()}")
        session.add(org)
        await session.flush()

        m1 = MethodologyVersion(code=f"iso14064_3_{uuid.uuid4()}")
        m2 = MethodologyVersion(code=f"ipcc_ar6_{uuid.uuid4()}")
        session.add_all([m1, m2])
        await session.flush()

        material_code = f"CEM_TEST_{uuid.uuid4().hex[:8]}"

        # Emission factors for cement under different methodologies.
        now = datetime.now(timezone.utc)

        ef1 = EmissionFactor(
            material_code=material_code,
            material_name="Cement",
            version=1,
            co2e_per_unit=Decimal("0.900000"),
            unit="kg",
            source_type="National",
            jurisdiction="GLOBAL",
            methodology_reference=m1.code,
            valid_from=now - timedelta(days=365),
            valid_to=None,
            factor_hash="",
            is_active=False,
            created_by="test",
            created_by_user_id=pm.id,
        )
        ef1.factor_hash = ef1.generate_hash()
        ef1.activate()

        ef2 = EmissionFactor(
            material_code=material_code,
            material_name="Cement",
            version=2,
            co2e_per_unit=Decimal("0.600000"),
            unit="kg",
            source_type="National",
            jurisdiction="GLOBAL",
            methodology_reference=m2.code,
            valid_from=now - timedelta(days=365),
            valid_to=None,
            factor_hash="",
            is_active=False,
            created_by="test",
            created_by_user_id=pm.id,
        )
        ef2.factor_hash = ef2.generate_hash()
        ef2.activate()

        session.add_all([ef1, ef2])
        await session.flush()

        project = Project(
            name=f"AcctCtx Project {uuid.uuid4()}",
            status=ProjectStatus.ACTIVE,
            lat=1.0,
            lon=1.0,
            budget_usd=1000.0,
            created_by=pm.id,
        )
        session.add(project)
        await session.flush()

        # Reporting entity owns 50% (equity boundary).
        rel = OrganizationRelationship(
            project_id=project.id,
            organization_id=org.id,
            role_type=OrganizationRoleType.DEVELOPER,
            ownership_percentage=Decimal("50.00"),
            financial_control=False,
            operational_control=False,
            valid_from=now - timedelta(days=1),
            valid_to=None,
        )
        session.add(rel)
        await session.flush()

        # One redeemed material token: 1000 kg of cement -> emissions differ by methodology.
        supplier = Supplier(
            name=f"Supplier {uuid.uuid4()}",
            partnership_discount=Decimal("0.0000"),
            total_value_supplied=Decimal("0.00"),
        )
        session.add(supplier)
        await session.flush()

        token = MaterialToken(
            project_id=project.id,
            material_code=material_code,
            material_name="Cement",
            quantity=Decimal("1000.000"),
            unit="kg",
            supplier_name=supplier.name,
            supplier_id=supplier.id,
            issued_by=pm.email,
            redeemed=True,
            redeemed_at=now,
            delivery_timestamp=now,
            delivery_lat=1.0,
            delivery_lon=1.0,
        )
        session.add(token)
        await session.flush()

        ctx1 = ReportingContext(
            reporting_entity_id=org.id,
            consolidation_method=ConsolidationMethod.EQUITY,
            reporting_purpose=ReportingPurpose.ESG,
            methodology_version_id=m1.id,
            valid_from=now - timedelta(days=2),
            valid_to=now + timedelta(days=2),
        )
        ctx2 = ReportingContext(
            reporting_entity_id=org.id,
            consolidation_method=ConsolidationMethod.EQUITY,
            reporting_purpose=ReportingPurpose.ESG,
            methodology_version_id=m2.id,
            valid_from=now - timedelta(days=2),
            valid_to=now + timedelta(days=2),
        )
        session.add_all([ctx1, ctx2])
        await session.flush()

        await session.commit()

        pm_id = pm.id
        pm_email = pm.email
        project_id = project.id
        ctx1_id = ctx1.id
        ctx2_id = ctx2.id

    client = TestClient(app)

    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        user_id=pm_id,
        email=pm_email,
        role_name=RoleName.PROJECT_MANAGER,
    )

    res1 = client.post(
        "/api/v1/reports/generate",
        json={"project_id": str(project_id), "reporting_context_id": str(ctx1_id)},
    )
    assert res1.status_code == 201, res1.text

    res2 = client.post(
        "/api/v1/reports/generate",
        json={"project_id": str(project_id), "reporting_context_id": str(ctx2_id)},
    )
    assert res2.status_code == 201, res2.text

    t1 = Decimal(str(res1.json()["total_emissions"]))
    t2 = Decimal(str(res2.json()["total_emissions"]))

    # 1000 kg * 0.9 = 900 kg = 0.9 t; equity 50% => 0.45 t
    assert t1 == Decimal("0.450000")
    # 1000 kg * 0.6 = 600 kg = 0.6 t; equity 50% => 0.3 t
    assert t2 == Decimal("0.300000")

    assert t1 != t2

    app.dependency_overrides = {}
