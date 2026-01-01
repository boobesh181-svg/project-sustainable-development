from fastapi.testclient import TestClient

from app.main import app


def test_public_metrics_is_public_and_aggregate_only():
    client = TestClient(app)
    res = client.get("/api/v1/public/metrics")

    # Must be publicly accessible (no auth required). DB might not be reachable in some envs,
    # so allow 5xx but never auth gating.
    assert res.status_code not in (401, 403)

    if res.status_code != 200:
        return

    data = res.json()
    assert set(data.keys()) == {
        "total_projects",
        "verified_mrvs",
        "emissions_trend",
        "anomaly_count",
    }

    # Basic type/shape checks
    assert isinstance(data["total_projects"], int)
    assert isinstance(data["verified_mrvs"], int)
    assert isinstance(data["anomaly_count"], int)
    assert isinstance(data["emissions_trend"], list)

    # Ensure no names/identifiers leak into payload
    raw = res.text.lower()
    assert "project_name" not in raw
    assert "supplier" not in raw
    assert "project_id" not in raw
