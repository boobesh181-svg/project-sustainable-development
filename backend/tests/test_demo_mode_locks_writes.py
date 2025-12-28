import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


@pytest.fixture
def client():
    return TestClient(app)


def test_demo_mode_locks_non_auth_posts(client):
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        # Should be locked (POST to a non-auth write endpoint)
        res = client.post("/api/v1/mrv-approval/reports")
        assert res.status_code == 423
        assert "Demo mode" in (res.json().get("detail") or "")

        # Auth login must still be possible (middleware should not block it)
        # Note: may still 400/401 depending on DB/users; just ensure it's NOT demo-locked.
        res2 = client.post("/api/v1/auth/login", json={"email": "x", "password": "y"})
        assert res2.status_code != 423
    finally:
        settings.DEMO_MODE = prev
