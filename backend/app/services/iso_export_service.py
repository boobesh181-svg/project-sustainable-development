from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.emission_factor import EmissionFactor
from app.models.evidence import Evidence
from app.models.mrv_report import MRVReport
from app.models.role import Role
from app.models.user import User
from app.core.config import settings


@dataclass(frozen=True)
class ExportPackage:
    filename: str
    content_type: str
    data: bytes


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_default(obj: Any):
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


def _to_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _safe_num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        return float(v)
    except Exception:
        return None


def _anon_user_label(i: int) -> str:
    return f"user_{i:03d}"


def _csv_bytes(rows: list[dict[str, Any]], *, fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in fieldnames})
    return buf.getvalue().encode("utf-8")


async def build_iso_export_payload(db: AsyncSession) -> dict[str, Any]:
    """Build the ISO export payload as a JSON-serializable dict (no binary packaging)."""

    reports_result = await db.execute(
        select(MRVReport)
        .options(selectinload(MRVReport.emission_factor))
        .order_by(MRVReport.created_at.asc())
    )
    reports = list(reports_result.scalars().all())

    ef_result = await db.execute(select(EmissionFactor).order_by(EmissionFactor.created_at.asc()))
    emission_factors = list(ef_result.scalars().all())

    evidence_result = await db.execute(select(Evidence).order_by(Evidence.created_at.asc()))
    evidence_rows = list(evidence_result.scalars().all())

    audit_result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "MRVReport",
            AuditLog.action.in_(
                [
                    "MRV_CREATED",
                    "MRV_SUBMITTED",
                    "MRV_VERIFIED",
                    "MRV_APPROVED",
                    "MRV_LOCKED",
                ]
            ),
        )
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    )
    audit_rows = list(audit_result.scalars().all())

    # ---- anonymization map (only for roles; no emails/names) ----
    user_ids: set[str] = set()
    for r in reports:
        user_ids.add(str(r.created_by))
        if r.verified_by:
            user_ids.add(str(r.verified_by))
        if r.approved_by:
            user_ids.add(str(r.approved_by))
    for ef in emission_factors:
        if ef.created_by_user_id:
            user_ids.add(str(ef.created_by_user_id))
    for ev in evidence_rows:
        if ev.created_by:
            user_ids.add(str(ev.created_by))
        if ev.verified_by:
            user_ids.add(str(ev.verified_by))
    for al in audit_rows:
        if al.actor_user_id:
            user_ids.add(str(al.actor_user_id))

    user_role_map: dict[str, str] = {}
    if user_ids:
        users_result = await db.execute(
            select(User.id, Role.name)
            .join(Role, Role.id == User.role_id)
            .where(User.id.in_([uuid_from_str(u) for u in user_ids]))
        )
        for uid, role_name in users_result.all():
            user_role_map[str(uid)] = getattr(role_name, "value", str(role_name))

    anon_map: dict[str, str] = {}
    for idx, uid in enumerate(sorted(user_ids), start=1):
        anon_map[uid] = _anon_user_label(idx)

    def anon(uid: Any) -> str | None:
        if uid is None:
            return None
        return anon_map.get(str(uid))

    def anon_role(uid: Any) -> str | None:
        if uid is None:
            return None
        return user_role_map.get(str(uid))

    # ---- approval chain per report (audit-derived timestamps) ----
    audit_by_report: dict[str, list[dict[str, Any]]] = {}
    for al in audit_rows:
        rid = al.entity_id
        audit_by_report.setdefault(rid, []).append(
            {
                "action": al.action,
                "timestamp": _to_iso(al.created_at),
                "actor": anon(al.actor_user_id),
                "actor_role": anon_role(al.actor_user_id),
                "event_hash": al.event_hash,
                "chain_hash": al.chain_hash,
                "prev_hash": al.prev_hash,
            }
        )

    payload: dict[str, Any] = {
        "export_type": "iso_compliance_package",
        "generated_at": _utc_now_iso(),
        "schema_version": "2025-12-27",
        "demo_mode": bool(settings.DEMO_MODE),
        "watermark": "DEMO - No real compliance claims" if settings.DEMO_MODE else None,
        "users": [
            {
                "user": anon_map[uid],
                "role": user_role_map.get(uid),
            }
            for uid in sorted(user_ids)
        ],
        "emission_factors": [
            {
                "id": str(ef.id),
                "material_code": ef.material_code,
                "material_name": ef.material_name,
                "version": int(ef.version),
                "co2e_per_unit": _safe_num(ef.co2e_per_unit),
                "unit": ef.unit,
                "valid_from": _to_iso(ef.valid_from),
                "valid_to": _to_iso(ef.valid_to),
                "factor_hash": ef.factor_hash,
                "is_active": bool(ef.is_active),
                "created_at": _to_iso(ef.created_at),
                "created_by_user": anon(ef.created_by_user_id),
                "created_by_role": anon_role(ef.created_by_user_id),
            }
            for ef in emission_factors
        ],
        "evidence": [
            {
                "id": str(ev.id),
                "upload_type": ev.upload_type,
                "sha256": ev.sha256,
                "size_bytes": int(ev.size_bytes),
                "content_type": ev.content_type,
                "original_filename": ev.original_filename,
                "created_at": _to_iso(ev.created_at),
                "created_by_user": anon(ev.created_by),
                "created_by_role": anon_role(ev.created_by),
                "verified_at": _to_iso(ev.verified_at),
                "verified_by_user": anon(ev.verified_by),
                "verified_by_role": anon_role(ev.verified_by),
                "decision": ev.decision,
                "verification_notes": ev.verification_notes,
                "report_id": str(ev.report_id) if ev.report_id else None,
                "material_token_id": str(ev.material_token_id) if ev.material_token_id else None,
            }
            for ev in evidence_rows
        ],
        "mrv_reports": [
            {
                "id": str(r.id),
                "project_id": str(r.project_id),
                "reporting_period": r.reporting_period,
                "sample_desc": r.sample_desc,
                "parameter": r.parameter,
                "value": r.value,
                "total_co2e": _safe_num(r.total_co2e),
                "status": r.status.value,
                "created_at": _to_iso(r.created_at),
                "updated_at": _to_iso(r.updated_at),
                "created_by_user": anon(r.created_by),
                "created_by_role": anon_role(r.created_by),
                "verified_by_user": anon(r.verified_by),
                "verified_by_role": anon_role(r.verified_by),
                "approved_by_user": anon(r.approved_by),
                "approved_by_role": anon_role(r.approved_by),
                "emission_factor_id": str(r.emission_factor_id) if r.emission_factor_id else None,
                "emission_factor_version_snapshot": r.emission_factor_version_snapshot,
                "emission_factor_hash_snapshot": r.emission_factor_hash_snapshot,
                "emission_factor_value_snapshot": _safe_num(r.emission_factor_value_snapshot),
                "certificate_path": r.certificate_path,
                "approval_chain": audit_by_report.get(str(r.id), []),
            }
            for r in reports
        ],
    }

    return payload


async def build_iso_compliance_package(
    db: AsyncSession,
    *,
    include_csv: bool = True,
    include_json: bool = True,
) -> ExportPackage:
    """Build an ISO/compliance export package.

    Package includes:
    - MRV reports
    - Emission factors (with hashes)
    - Evidence metadata (no raw files)
    - Approval chain (from audit logs)
    - Timestamps
    - User roles (anonymized)
    """

    export_json: dict[str, Any] = await build_iso_export_payload(db)

    # ---- CSV tables ----
    csv_files: dict[str, bytes] = {}
    if include_csv:
        csv_files["mrv_reports.csv"] = _csv_bytes(
            export_json["mrv_reports"],
            fieldnames=[
                "id",
                "project_id",
                "reporting_period",
                "sample_desc",
                "parameter",
                "value",
                "total_co2e",
                "status",
                "created_at",
                "updated_at",
                "created_by_user",
                "created_by_role",
                "verified_by_user",
                "verified_by_role",
                "approved_by_user",
                "approved_by_role",
                "emission_factor_id",
                "emission_factor_version_snapshot",
                "emission_factor_hash_snapshot",
                "emission_factor_value_snapshot",
            ],
        )
        csv_files["emission_factors.csv"] = _csv_bytes(
            export_json["emission_factors"],
            fieldnames=[
                "id",
                "material_code",
                "material_name",
                "version",
                "co2e_per_unit",
                "unit",
                "valid_from",
                "valid_to",
                "factor_hash",
                "is_active",
                "created_at",
                "created_by_user",
                "created_by_role",
            ],
        )
        csv_files["evidence.csv"] = _csv_bytes(
            export_json["evidence"],
            fieldnames=[
                "id",
                "upload_type",
                "sha256",
                "size_bytes",
                "content_type",
                "original_filename",
                "created_at",
                "created_by_user",
                "created_by_role",
                "verified_at",
                "verified_by_user",
                "verified_by_role",
                "decision",
                "verification_notes",
                "report_id",
                "material_token_id",
            ],
        )

        # Flatten approval chain
        approval_rows: list[dict[str, Any]] = []
        for report in export_json["mrv_reports"]:
            for step in report.get("approval_chain", []) or []:
                approval_rows.append(
                    {
                        "report_id": report["id"],
                        "action": step.get("action"),
                        "timestamp": step.get("timestamp"),
                        "actor": step.get("actor"),
                        "actor_role": step.get("actor_role"),
                        "event_hash": step.get("event_hash"),
                        "chain_hash": step.get("chain_hash"),
                        "prev_hash": step.get("prev_hash"),
                    }
                )
        csv_files["approval_chain.csv"] = _csv_bytes(
            approval_rows,
            fieldnames=[
                "report_id",
                "action",
                "timestamp",
                "actor",
                "actor_role",
                "event_hash",
                "chain_hash",
                "prev_hash",
            ],
        )

        csv_files["users_anonymized.csv"] = _csv_bytes(
            export_json["users"],
            fieldnames=["user", "role"],
        )

    # ---- ZIP ----
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"mrv_compliance_package_{now}.zip"
    if settings.DEMO_MODE:
        filename = f"DEMO_{filename}"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if settings.DEMO_MODE:
            zf.writestr(
                "DEMO_NOTICE.txt",
                "DEMO MODE - No real compliance claims. This export is synthetic and for pilot evaluation only.\n",
            )
        if include_json:
            zf.writestr("iso_export.json", json.dumps(export_json, indent=2, default=_json_default))
        for name, content in csv_files.items():
            zf.writestr(name, content)

    return ExportPackage(filename=filename, content_type="application/zip", data=buf.getvalue())


def uuid_from_str(value: str):
    import uuid

    return uuid.UUID(value)
