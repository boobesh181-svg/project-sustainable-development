import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.main import app
from app.models.role import Role, RoleName


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

            import datetime

            self.created_at = datetime.datetime(2025, 12, 25, 0, 0, 0, tzinfo=datetime.timezone.utc)

    return DummyUser()


def test_iso_export_requires_auth():
    client = TestClient(app)
    res = client.get("/api/v1/mrv/export/iso")
    # auth dependency should block unauthenticated access
    assert res.status_code in (401, 403)


@pytest.mark.parametrize("fmt", ["zip", "json"])
def test_iso_export_blocks_supplier(fmt: str):
    client = TestClient(app)
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "supplier@example.com", RoleName.SUPPLIER
    )

    res = client.get(f"/api/v1/mrv/export/iso?format={fmt}")
    assert res.status_code == 403

    app.dependency_overrides = {}


@pytest.mark.parametrize("fmt", ["zip", "json"])
def test_iso_export_allows_privileged_roles_through_rbac_layer(fmt: str):
    """This test only checks RBAC gating; the handler may still 500 if DB isn't initialized."""

    client = TestClient(app)
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        "admin@example.com", RoleName.ADMIN
    )

    res = client.get(f"/api/v1/mrv/export/iso?format={fmt}")
    assert res.status_code != 403

    app.dependency_overrides = {}
