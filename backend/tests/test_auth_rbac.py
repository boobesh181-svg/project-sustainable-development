import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import deps
from app.models.role import Role, RoleName


@pytest.fixture
def client():
    return TestClient(app)


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

            # auth/me uses created_at isoformat
            import datetime

            self.created_at = datetime.datetime(2025, 12, 25, 0, 0, 0, tzinfo=datetime.timezone.utc)

    return DummyUser()


def test_me_serialization_ok(client):
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "admin@example.com", RoleName.ADMIN
    )

    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "admin@example.com"
    assert data["role"] == "admin"
    assert isinstance(data["id"], str)
    assert isinstance(data["created_at"], str)

    app.dependency_overrides = {}


def test_dashboard_requires_auth(client):
    # With no auth dependency override, get_current_user should reject
    res = client.get("/api/v1/dashboard/summary")
    assert res.status_code in (401, 403)


def test_audit_logs_requires_privileged_role(client):
    # non-privileged user should be blocked
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "supplier@example.com", RoleName.SUPPLIER
    )

    res = client.get("/api/v1/audit-logs/")
    assert res.status_code == 403

    # privileged should pass auth layer; response may still fail if DB not configured for tests
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "admin@example.com", RoleName.ADMIN
    )

    res2 = client.get("/api/v1/audit-logs/?limit=1")
    assert res2.status_code != 403

    app.dependency_overrides = {}
