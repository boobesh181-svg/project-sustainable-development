import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.main import app
from app.core.config import settings
from app.services.mrv_approval_service import advance_mrv_status
from app.services.mrv_approval_service import create_mrv_report
from app.services.emission_calc_service import activate_emission_factor
from app.services.emission_calc_service import create_emission_factor
from app.services.material_service import issue_material_token, redeem_material_token
from app.services.delivery_service import create_delivery_verification, approve_delivery_verification
from app.services.evidence_service import verify_evidence
from app.services.anomaly_engine import run_anomaly_checks

from app.schemas.mrv_approval import MRVReportCreate
from app.schemas.emission_factor import EmissionFactorCreate
from app.schemas.material import MaterialTokenCreate, MaterialTokenRedeem
from app.schemas.delivery import DeliveryVerificationCreate, DeliveryVerificationApprove
from app.schemas.evidence import EvidenceVerify


@pytest.fixture
def client():
    return TestClient(app)


def test_demo_mode_blocks_destructive_verbs_in_middleware(client):
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        # Coarse safety net: destructive verbs are blocked even if route doesn't exist.
        res = client.delete("/api/v1/projects/does-not-matter")
        assert res.status_code == 403
        assert "Demo mode" in (res.json().get("detail") or "")

        # Auth login must still be possible (middleware should not block it)
        # Note: may still 400/401 depending on DB/users; just ensure it's NOT demo-locked.
        res2 = client.post("/api/v1/auth/login", json={"email": "x", "password": "y"})
        assert res2.status_code != 403
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_mrv_advance_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def execute(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        with pytest.raises(HTTPException) as exc:
            await advance_mrv_status(
                db=_DB(),
                report_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                next_status="SUBMITTED",
                actor="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                actor_role=None,
            )
        assert exc.value.status_code == 403
        assert "MRV workflow advancement" in (exc.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_emission_factor_activation_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def get(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        with pytest.raises(HTTPException) as exc:
            await activate_emission_factor(db=_DB(), factor_id="deadbeef")
        assert exc.value.status_code == 403
        assert "emission factor activation" in (exc.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_mrv_report_create_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def execute(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        payload = MRVReportCreate(
            project_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            reporting_period="2026-01",
            sample_desc="x",
            parameter="CO2",
            value="1.0",
            total_co2e=1.0,
            created_by="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            emission_factor_id=None,
            certificate_path=None,
        )

        with pytest.raises(HTTPException) as exc:
            await create_mrv_report(_DB(), payload)
        assert exc.value.status_code == 403
        assert "MRV report creation" in (exc.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_emission_factor_create_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def execute(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        payload = EmissionFactorCreate(
            material_code="CEM1",
            material_name="Cement",
            version=1,
            co2e_per_unit=1.0,
            unit="kg",
            valid_from="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
            valid_to=None,
        )

        with pytest.raises(HTTPException) as exc:
            await create_emission_factor(
                _DB(),
                payload,
                actor_user_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                actor_email="x@example.com",
            )
        assert exc.value.status_code == 403
        assert "emission factor creation" in (exc.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_material_token_issue_and_redeem_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def execute(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

            async def commit(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

            async def refresh(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

            def add(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        issue_payload = MaterialTokenCreate(
            project_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            material_code="STEEL",
            material_name="Steel",
            quantity=1.0,
            unit="kg",
            supplier_name="Demo Supplier",
            issued_by="system",
        )
        with pytest.raises(HTTPException) as exc1:
            await issue_material_token(
                _DB(),
                issue_payload,
                actor_email="x@example.com",
                actor_user_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            )
        assert exc1.value.status_code == 403
        assert "issuance" in (exc1.value.detail or "")

        redeem_payload = MaterialTokenRedeem(
            delivery_lat=1.0,
            delivery_lon=2.0,
            supplier_invoice_ref="INV",
        )
        with pytest.raises(HTTPException) as exc2:
            await redeem_material_token(
                _DB(),
                token_uid="T1",
                payload=redeem_payload,
                delivery_photo_path="x.jpg",
                actor="x",
                actor_user_id=None,
            )
        assert exc2.value.status_code == 403
        assert "redemption" in (exc2.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_delivery_verification_create_and_approve_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def execute(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        create_payload = DeliveryVerificationCreate(
            material_token_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
            photo_path="x.jpg",
            delivery_lat=1.0,
            delivery_lon=2.0,
        )
        with pytest.raises(HTTPException) as exc1:
            await create_delivery_verification(
                _DB(),
                create_payload,
                actor_user_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                actor_email="x@example.com",
            )
        assert exc1.value.status_code == 403
        assert "delivery verification creation" in (exc1.value.detail or "")

        approve_payload = DeliveryVerificationApprove(verified_by=None, verification_notes="x")
        with pytest.raises(HTTPException) as exc2:
            await approve_delivery_verification(
                _DB(),
                verification_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                data=approve_payload,
                actor_user_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                actor_email="x@example.com",
            )
        assert exc2.value.status_code == 403
        assert "delivery verification approval" in (exc2.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_blocks_evidence_verification_in_service_layer():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _DB:
            async def get(self, *args, **kwargs):  # pragma: no cover
                raise AssertionError("DB should not be used when demo guard triggers")

        payload = EvidenceVerify(decision="approve", verification_notes="x")
        with pytest.raises(HTTPException) as exc:
            await verify_evidence(
                _DB(),
                evidence_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                payload=payload,
                actor_user_id="00000000-0000-0000-0000-000000000000",  # type: ignore[arg-type]
                actor_email="x@example.com",
            )
        assert exc.value.status_code == 403
        assert "evidence verification" in (exc.value.detail or "")
    finally:
        settings.DEMO_MODE = prev


@pytest.mark.asyncio
async def test_demo_mode_allows_anomaly_checks_only_for_demo_projects():
    prev = settings.DEMO_MODE
    settings.DEMO_MODE = True
    try:
        class _Result:
            def __init__(self, obj):
                self._obj = obj

            def scalar_one_or_none(self):
                return self._obj

            def scalar(self):
                return self._obj

        class _Token:
            project_id = "P1"
            id = "TID"
            token_uid = "TOK"
            quantity = 1.0
            unit = "kg"
            supplier_name = "Demo Supplier"

            from datetime import datetime, timezone

            issued_at = datetime.now(timezone.utc)

        class _Project:
            def __init__(self, name: str):
                self.name = name

        class _DB:
            def __init__(self, project_name: str):
                self.project_name = project_name
                self.calls = 0

            async def commit(self):
                return None

            async def execute(self, *args, **kwargs):
                # Called for: token lookup, project lookup, delivery lookup
                self.calls += 1
                if self.calls == 1:
                    return _Result(_Token())
                if self.calls == 2:
                    return _Result(_Project(self.project_name))
                # delivery lookup
                if self.calls == 3:
                    return _Result(None)
                # supplier frequency count
                return _Result(0)

        with pytest.raises(HTTPException) as exc:
            await run_anomaly_checks(_DB("Real Project"), token_uid="X")
        assert exc.value.status_code == 403

        # DEMO projects should proceed (and return an empty list with this stub DB)
        res = await run_anomaly_checks(_DB("DEMO Project"), token_uid="X")
        assert res == []
    finally:
        settings.DEMO_MODE = prev
