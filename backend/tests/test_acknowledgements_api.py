import socket
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
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
from app.models.activity_record import ActivityRecord, ActivityType
from app.models.event_notification import EventNotification
from app.models.event_notification import DeliveryChannel
from app.models.material_token import MaterialToken
from app.models.project import Project, ProjectStatus
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


async def _create_user(session, *, role: Role, email_prefix: str, supplier_id: uuid.UUID | None = None) -> User:
    user = User(
        email=f"{email_prefix}+{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        full_name=email_prefix,
        is_active=True,
        role_id=role.id,
        supplier_id=supplier_id,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_delivery_verification_emits_ack_notification_and_ack_flow():
    # Arrange: create DB state.
    async with AsyncSessionLocal() as session:
        await session.begin()

        contractor_role = await _get_or_create_role(session, RoleName.CONTRACTOR)
        supplier_role = await _get_or_create_role(session, RoleName.SUPPLIER)

        supplier = Supplier(
            name=f"Test Supplier {uuid.uuid4()}",
            partnership_discount=0,
            total_value_supplied=0,
        )
        session.add(supplier)
        await session.flush()

        contractor = await _create_user(session, role=contractor_role, email_prefix="contractor")
        supplier_user = await _create_user(
            session,
            role=supplier_role,
            email_prefix="supplier",
            supplier_id=supplier.id,
        )

        project = Project(
            name=f"Ack DV Project {uuid.uuid4()}",
            status=ProjectStatus.ACTIVE,
            lat=1.0,
            lon=1.0,
            budget_usd=1000.0,
            created_by=contractor.id,
        )
        session.add(project)
        await session.flush()

        now = datetime.now(timezone.utc)
        token = MaterialToken(
            project_id=project.id,
            material_code="CEM",
            material_name="Cement",
            quantity=1.0,
            unit="t",
            supplier_name=supplier.name,
            supplier_id=supplier.id,
            issued_by=contractor.email,
            redeemed=False,
            delivery_photo_path="uploads/material_evidence/test.jpg",
            delivery_lat=10.0,
            delivery_lon=20.0,
            supplier_invoice_ref="INV-TEST",
            delivery_timestamp=now,
        )
        token.redeem()
        session.add(token)
        await session.flush()

        await session.commit()

    # Create a real file path for delivery verification fingerprinting.
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        tmp.write(b"test image content")
        tmp.flush()
        tmp.close()

        # Act: call delivery verification creation API as contractor.
        client = TestClient(app)
        app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
            user_id=contractor.id,
            email=contractor.email,
            role_name=RoleName.CONTRACTOR,
        )

        res = client.post(
            "/api/v1/deliveries/verify",
            json={
                "material_token_id": str(token.id),
                "photo_path": tmp.name,
                "delivery_lat": 10.0,
                "delivery_lon": 20.0,
            },
        )
        assert res.status_code == 201, res.text
        verification_id = res.json()["id"]

        # Assert: activity + notification created (best-effort integration).
        async with AsyncSessionLocal() as session:
            activity = (
                await session.execute(
                    select(ActivityRecord)
                    .where(
                        ActivityRecord.activity_type == ActivityType.DELIVERY_VERIFICATION_CREATED,
                        ActivityRecord.delivery_verification_id == uuid.UUID(verification_id),
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            assert activity is not None

            notif = (
                await session.execute(
                    select(EventNotification)
                    .where(
                        EventNotification.activity_id == activity.id,
                        EventNotification.notified_user_id == supplier_user.id,
                    )
                    .order_by(EventNotification.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            assert notif is not None

        # Act: supplier lists pending notifications and acknowledges.
        app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
            user_id=supplier_user.id,
            email=supplier_user.email,
            role_name=RoleName.SUPPLIER,
        )

        pending = client.get("/api/v1/notifications/pending").json()
        assert isinstance(pending, list)
        assert len(pending) >= 1
        target = next((n for n in pending if n["activity_id"] == str(activity.id)), None)
        assert target is not None

        resp = client.post(
            f"/api/v1/notifications/{target['id']}/respond",
            json={"response_type": "acknowledge", "response_comment": None},
        )
        assert resp.status_code == 201, resp.text

        status_res = client.get(f"/api/v1/events/{activity.id}/acknowledgement-status")
        assert status_res.status_code == 200, status_res.text
        assert status_res.json()["derived_status"] == "ACKNOWLEDGED"

    finally:
        app.dependency_overrides = {}
        try:
            import os

            os.unlink(tmp.name)
        except Exception:
            pass


@pytest.mark.asyncio
async def test_mrv_report_created_emits_ack_notification_and_ack_flow():
    # Arrange: create DB state (contractor + MRV officer + project).
    async with AsyncSessionLocal() as session:
        await session.begin()

        contractor_role = await _get_or_create_role(session, RoleName.CONTRACTOR)
        officer_role = await _get_or_create_role(session, RoleName.MRV_OFFICER)

        contractor = await _create_user(session, role=contractor_role, email_prefix="contractor")
        officer = await _create_user(session, role=officer_role, email_prefix="officer")

        project = Project(
            name=f"Ack MRV Project {uuid.uuid4()}",
            status=ProjectStatus.ACTIVE,
            lat=1.0,
            lon=1.0,
            budget_usd=1000.0,
            created_by=contractor.id,
        )
        session.add(project)
        await session.flush()
        await session.commit()

    client = TestClient(app)

    # Act: create MRV report as contractor.
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
            "sample_desc": "Sample",
            "parameter": "cement",
            "value": "100",
            "total_co2e": 1.2345,
            "emission_factor_id": None,
            "certificate_path": None,
        },
    )
    assert res.status_code == 201, res.text
    report_id = res.json()["id"]

    # Assert: activity + notification created (best-effort integration).
    async with AsyncSessionLocal() as session:
        activity = (
            await session.execute(
                select(ActivityRecord)
                .where(
                    ActivityRecord.activity_type == ActivityType.MRV_REPORT_CREATED,
                    ActivityRecord.mrv_report_id == uuid.UUID(report_id),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        assert activity is not None

        notif = (
            await session.execute(
                select(EventNotification)
                .where(EventNotification.activity_id == activity.id)
                .order_by(EventNotification.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        assert notif is not None

        notified_user = await session.get(User, notif.notified_user_id)
        assert notified_user is not None
        notified_role = (
            await session.execute(
                select(Role.name)
                .join(User, User.role_id == Role.id)
                .where(User.id == notif.notified_user_id)
                .limit(1)
            )
        ).scalar_one_or_none()
        assert notified_role == RoleName.MRV_OFFICER

    # Act: MRV officer acknowledges.
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        user_id=notified_user.id,
        email=notified_user.email,
        role_name=RoleName.MRV_OFFICER,
    )

    pending = client.get("/api/v1/notifications/pending").json()
    assert isinstance(pending, list)
    target = next((n for n in pending if n["activity_id"] == str(activity.id)), None)
    assert target is not None

    resp = client.post(
        f"/api/v1/notifications/{target['id']}/respond",
        json={"response_type": "acknowledge", "response_comment": None},
    )
    assert resp.status_code == 201, resp.text

    status_res = client.get(f"/api/v1/events/{activity.id}/acknowledgement-status")
    assert status_res.status_code == 200, status_res.text
    assert status_res.json()["derived_status"] == "ACKNOWLEDGED"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_expired_notification_auto_no_response_becomes_deemed_observed():
    # Arrange: create an activity + an already-expired notification with no responses.
    async with AsyncSessionLocal() as session:
        await session.begin()

        contractor_role = await _get_or_create_role(session, RoleName.CONTRACTOR)
        supplier_role = await _get_or_create_role(session, RoleName.SUPPLIER)

        actor = await _create_user(session, role=contractor_role, email_prefix="actor")
        counterparty = await _create_user(session, role=supplier_role, email_prefix="counterparty")

        project = Project(
            name=f"Ack Expiry Project {uuid.uuid4()}",
            status=ProjectStatus.ACTIVE,
            lat=1.0,
            lon=1.0,
            budget_usd=1000.0,
            created_by=actor.id,
        )
        session.add(project)
        await session.flush()

        token = MaterialToken(
            project_id=project.id,
            material_code="CEM",
            material_name="Cement",
            quantity=1.0,
            unit="t",
            supplier_name="Test Supplier",
            supplier_id=None,
            issued_by=actor.email,
            redeemed=False,
        )
        session.add(token)
        await session.flush()

        occurred = datetime.now(timezone.utc).replace(microsecond=0)
        activity = ActivityRecord(
            activity_type=ActivityType.MATERIAL_TOKEN_REDEEMED,
            project_id=project.id,
            material_token_id=token.id,
            delivery_verification_id=None,
            mrv_report_id=None,
            occurred_at=occurred,
            created_by_user_id=actor.id,
            activity_hash=ActivityRecord.compute_hash(
                activity_type=ActivityType.MATERIAL_TOKEN_REDEEMED,
                project_id=project.id,
                occurred_at=occurred,
                material_token_id=token.id,
                delivery_verification_id=None,
                mrv_report_id=None,
                created_by_user_id=actor.id,
            ),
        )
        session.add(activity)
        await session.flush()

        notification_ts = occurred - timedelta(hours=2)
        deadline_ts = occurred - timedelta(hours=1)
        notif = EventNotification(
            activity_id=activity.id,
            notified_party_org_id=None,
            notified_user_id=counterparty.id,
            notification_timestamp=notification_ts,
            response_deadline_timestamp=deadline_ts,
            notification_hash=EventNotification.compute_hash(
                activity_id=activity.id,
                notified_user_id=counterparty.id,
                notification_timestamp=notification_ts,
                response_deadline_timestamp=deadline_ts,
                delivery_channel=DeliveryChannel.IN_APP,
                demo_watermark=bool(settings.DEMO_MODE),
            ),
            delivery_channel=DeliveryChannel.IN_APP,
            demo_watermark=bool(settings.DEMO_MODE),
        )
        session.add(notif)
        await session.commit()

    client = TestClient(app)

    # Act: counterparty hits pending notifications (this should auto-append NO_RESPONSE_AUTO for expired entries).
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        user_id=counterparty.id,
        email=counterparty.email,
        role_name=RoleName.SUPPLIER,
    )

    pending = client.get("/api/v1/notifications/pending").json()
    assert isinstance(pending, list)
    assert next((n for n in pending if n["activity_id"] == str(activity.id)), None) is None

    # Assert: derived status becomes DEEMED_OBSERVED.
    status_res = client.get(f"/api/v1/events/{activity.id}/acknowledgement-status")
    assert status_res.status_code == 200, status_res.text
    assert status_res.json()["derived_status"] == "DEEMED_OBSERVED"

    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_dispute_response_sets_derived_status_disputed():
    # Arrange: create activity and send notification via API.
    async with AsyncSessionLocal() as session:
        await session.begin()

        contractor_role = await _get_or_create_role(session, RoleName.CONTRACTOR)
        supplier_role = await _get_or_create_role(session, RoleName.SUPPLIER)

        actor = await _create_user(session, role=contractor_role, email_prefix="actor")
        counterparty = await _create_user(session, role=supplier_role, email_prefix="counterparty")

        project = Project(
            name=f"Ack Dispute Project {uuid.uuid4()}",
            status=ProjectStatus.ACTIVE,
            lat=1.0,
            lon=1.0,
            budget_usd=1000.0,
            created_by=actor.id,
        )
        session.add(project)
        await session.flush()

        token = MaterialToken(
            project_id=project.id,
            material_code="CEM",
            material_name="Cement",
            quantity=1.0,
            unit="t",
            supplier_name="Test Supplier",
            supplier_id=None,
            issued_by=actor.email,
            redeemed=False,
        )
        session.add(token)
        await session.flush()

        occurred = datetime.now(timezone.utc).replace(microsecond=0)
        activity = ActivityRecord(
            activity_type=ActivityType.MATERIAL_TOKEN_REDEEMED,
            project_id=project.id,
            material_token_id=token.id,
            delivery_verification_id=None,
            mrv_report_id=None,
            occurred_at=occurred,
            created_by_user_id=actor.id,
            activity_hash=ActivityRecord.compute_hash(
                activity_type=ActivityType.MATERIAL_TOKEN_REDEEMED,
                project_id=project.id,
                occurred_at=occurred,
                material_token_id=token.id,
                delivery_verification_id=None,
                mrv_report_id=None,
                created_by_user_id=actor.id,
            ),
        )
        session.add(activity)
        await session.commit()

    client = TestClient(app)

    # Actor sends notification (explicit recipient).
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        user_id=actor.id,
        email=actor.email,
        role_name=RoleName.CONTRACTOR,
    )

    notify_res = client.post(
        f"/api/v1/events/{activity.id}/notify",
        json={"notified_user_id": str(counterparty.id), "delivery_channel": "in_app", "response_window_hours": 48},
    )
    assert notify_res.status_code == 201, notify_res.text
    notification_id = notify_res.json()["id"]

    # Counterparty disputes.
    app.dependency_overrides[deps.get_current_user] = lambda: _make_user(
        user_id=counterparty.id,
        email=counterparty.email,
        role_name=RoleName.SUPPLIER,
    )

    resp = client.post(
        f"/api/v1/notifications/{notification_id}/respond",
        json={"response_type": "dispute", "response_comment": "Disagree with this event."},
    )
    assert resp.status_code == 201, resp.text

    status_res = client.get(f"/api/v1/events/{activity.id}/acknowledgement-status")
    assert status_res.status_code == 200, status_res.text
    assert status_res.json()["derived_status"] == "DISPUTED"

    app.dependency_overrides = {}
