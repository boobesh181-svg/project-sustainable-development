import datetime
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import deps
from app.models.role import Role, RoleName


@pytest.fixture
def client():
    return TestClient(app)


async def _override_get_db():
    class DummyDB:
        pass

    yield DummyDB()


def _make_user(*, email: str, role_name: RoleName):
    class DummyUser:
        def __init__(self):
            self.id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            self.email = email
            self.full_name = "Test User"
            self.is_active = True

            r = Role()
            r.id = 1
            r.name = role_name
            self.role = r

            self.created_at = datetime.datetime(2025, 12, 25, 0, 0, 0, tzinfo=datetime.timezone.utc)

    return DummyUser()


def test_mrv_approval_create_requires_contractor_or_pm(client, monkeypatch):
    # Avoid real DB usage even for dependency resolution
    app.dependency_overrides[deps.get_db] = _override_get_db

    # Non-allowed role
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        email="supplier@example.com", role_name=RoleName.SUPPLIER
    )

    payload = {
        "project_id": str(uuid.uuid4()),
        "reporting_period": "2025-Q1",
        "sample_desc": "Test sample",
        "parameter": "cement",
        "value": "100",
        "total_co2e": 1.23,
    }

    res = client.post("/api/v1/mrv-approval/reports", json=payload)
    assert res.status_code == 403

    app.dependency_overrides = {}


def test_emission_factor_create_requires_admin(client):
    app.dependency_overrides[deps.get_db] = _override_get_db

    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        email="mrv@example.com", role_name=RoleName.MRV_OFFICER
    )

    payload = {
        "material_code": "TEST_MAT",
        "material_name": "Test Material",
        "version": 1,
        "co2e_per_unit": 1.0,
        "unit": "kg",
        "valid_from": "2025-01-01T00:00:00Z",
    }

    res = client.post("/api/v1/emission-factors/", json=payload)
    assert res.status_code == 403

    app.dependency_overrides = {}


def test_emission_factor_get_active_requires_auth(client):
    # Without auth override, get_current_user should reject.
    res = client.get("/api/v1/emission-factors/by-material/ANY")
    assert res.status_code in (401, 403)


def test_mrv_approval_list_requires_auth(client):
    res = client.get("/api/v1/mrv-approval/reports")
    assert res.status_code in (401, 403)
