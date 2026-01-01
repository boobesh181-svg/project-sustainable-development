from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_demo_walkthrough_state_returns_ordered_steps():
    client = TestClient(app)
    res = client.get("/api/v1/demo/walkthrough-state")
    assert res.status_code == 200

    data = res.json()
    assert "demo_mode" in data
    assert data["steps"] == [
        {"order": 1, "title": "Login"},
        {"order": 2, "title": "View seeded project"},
        {"order": 3, "title": "View MRV lifecycle (draft → approved)"},
        {"order": 4, "title": "View emission factor snapshot"},
        {"order": 5, "title": "View anomaly explanation"},
        {"order": 6, "title": "Export compliance bundle"},
    ]
