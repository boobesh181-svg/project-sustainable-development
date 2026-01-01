from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from starlette import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.emission_factor import EmissionFactor
from app.models.evidence import Evidence
from app.models.mrv_report import MRVReport, MRVStatus


@dataclass(frozen=True)
class ExportPackage:
    filename: str
    content_type: str
    data: bytes


_FIXED_ZIP_DATETIME = (1980, 1, 1, 0, 0, 0)


def _json_default(obj: Any):
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    return str(obj)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    # Deterministic JSON: stable key order, stable separators, no indentation.
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    ).encode("utf-8")


def _zip_writestr_deterministic(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(filename=name, date_time=_FIXED_ZIP_DATETIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    # Ensure consistent file permissions/attrs across environments.
    info.external_attr = 0o600 << 16
    zf.writestr(info, data)


def _safe_read_optional_file(path: str) -> bytes | None:
    # Optional PDF/attachment: include only if the path exists.
    # This keeps export deterministic for a given DB + filesystem state.
    if not path:
        return None
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return f.read()


async def build_mrv_report_export_payload(db: AsyncSession, report_id: UUID) -> dict[str, Any]:
    report = (
        await db.execute(
            select(MRVReport)
            .options(
                selectinload(MRVReport.emission_factor),
                selectinload(MRVReport.project),
            )
            .where(MRVReport.id == report_id)
        )
    ).scalar_one_or_none()

    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="MRV report not found")

    if report.status not in (MRVStatus.APPROVED, MRVStatus.LOCKED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Export is only available for APPROVED or LOCKED MRV reports",
        )

    audit_rows = list(
        (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.entity_type == "MRVReport",
                    AuditLog.entity_id == str(report.id),
                )
                .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
            )
        )
        .scalars()
        .all()
    )

    evidence_rows = list(
        (
            await db.execute(
                select(Evidence)
                .where(Evidence.report_id == report.id)
                .order_by(Evidence.created_at.asc(), Evidence.id.asc())
            )
        )
        .scalars()
        .all()
    )

    pilot_mode = bool(getattr(report, "pilot", False) or getattr(getattr(report, "project", None), "pilot", False))
    demo_mode = bool(settings.DEMO_MODE)

    # Guardrail: demo-only evidence must never appear in a non-demo/non-pilot export.
    if not demo_mode and not pilot_mode:
        if any(bool(getattr(ev, "demo_only", False)) for ev in evidence_rows):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Export blocked: demo-only evidence is attached to this report",
            )

    # Snapshot is the compliance-critical source of truth.
    snapshot = {
        "emission_factor_id": str(report.emission_factor_id) if report.emission_factor_id else None,
        "factor_hash": report.emission_factor_hash_snapshot,
        "factor_value": str(report.emission_factor_value_snapshot)
        if report.emission_factor_value_snapshot is not None
        else None,
        "factor_version": report.emission_factor_version_snapshot,
    }

    # Include referenced factor record for traceability (immutable once active; append-only).
    ef_record: dict[str, Any] | None = None
    ef = report.emission_factor
    if ef is not None:
        ef_record = {
            "id": str(ef.id),
            "material_code": ef.material_code,
            "material_name": ef.material_name,
            "version": int(ef.version),
            "co2e_per_unit": str(ef.co2e_per_unit),
            "unit": ef.unit,
            "source_type": getattr(ef, "source_type", None),
            "jurisdiction": getattr(ef, "jurisdiction", None),
            "methodology_reference": getattr(ef, "methodology_reference", None),
            "valid_from": ef.valid_from,
            "valid_to": ef.valid_to,
            "factor_hash": ef.factor_hash,
            "is_active": bool(ef.is_active),
            "created_at": ef.created_at,
            "created_by": ef.created_by,
            "created_by_user_id": str(ef.created_by_user_id)
            if ef.created_by_user_id
            else None,
        }

    # Deterministic export metadata: derived from report state, not wall-clock.
    # If you re-export the same report without DB changes, the output stays identical.
    export_metadata = {
        "export_type": "mrv_report_export",
        "schema_version": "2026-01-01",
        "demo_mode": demo_mode,
        "pilot": pilot_mode,
        "watermark": (
            "DEMO - No real compliance claims"
            if demo_mode
            else ("PILOT DATA - Not a compliance claim" if pilot_mode else None)
        ),
        "report_id": str(report.id),
        "report_status": report.status.value,
        "report_updated_at": report.updated_at.replace(microsecond=0).isoformat(),
    }

    payload: dict[str, Any] = {
        "meta": export_metadata,
        "mrv_summary": {
            "id": str(report.id),
            "project_id": str(report.project_id),
            "reporting_period": report.reporting_period,
            "sample_desc": report.sample_desc,
            "parameter": report.parameter,
            "value": report.value,
            "total_co2e": str(report.total_co2e),
            "status": report.status.value,
            "created_at": report.created_at,
            "updated_at": report.updated_at,
            "emission_factor_snapshot": snapshot,
            "certificate_path": report.certificate_path,
        },
        "emission_factor": {
            "snapshot": snapshot,
            "record": ef_record,
        },
        "audit_trail": [
            {
                "id": str(al.id),
                "action": al.action,
                "created_at": al.created_at,
                "actor_user_id": str(al.actor_user_id) if al.actor_user_id else None,
                "actor": al.actor,
                "event_hash": al.event_hash,
                "prev_hash": al.prev_hash,
                "chain_hash": al.chain_hash,
                "event_payload": al.event_payload,
            }
            for al in audit_rows
        ],
        "evidence_hashes": [
            {
                "id": str(ev.id),
                "upload_type": ev.upload_type,
                "evidence_hash": ev.evidence_hash,
                "sha256": ev.sha256,
                "size_bytes": int(ev.size_bytes),
                "content_type": ev.content_type,
                "original_filename": ev.original_filename,
                "created_at": ev.created_at,
                "created_by": str(ev.created_by) if ev.created_by else None,
                "verified_at": ev.verified_at,
                "verified_by": str(ev.verified_by) if ev.verified_by else None,
                "decision": ev.decision,
                "verification_notes": ev.verification_notes,
            }
            for ev in evidence_rows
        ],
    }

    return payload


async def build_mrv_report_export_package(db: AsyncSession, report_id: UUID) -> ExportPackage:
    payload = await build_mrv_report_export_payload(db, report_id)

    filename = f"mrv_report_export_{payload['meta']['report_id']}.zip"
    if payload.get("meta", {}).get("demo_mode"):
        filename = f"DEMO_{filename}"
    elif payload.get("meta", {}).get("pilot"):
        filename = f"PILOT_{filename}"

    # Optional PDF: include existing certificate file if present.
    cert_bytes: bytes | None = None
    cert_path = payload.get("mrv_summary", {}).get("certificate_path")
    if isinstance(cert_path, str) and cert_path:
        cert_bytes = _safe_read_optional_file(cert_path)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        if payload.get("meta", {}).get("demo_mode"):
            _zip_writestr_deterministic(
                zf,
                "DEMO_NOTICE.txt",
                b"DEMO MODE - No real compliance claims. This export is synthetic and for pilot evaluation only.\n",
            )
        elif payload.get("meta", {}).get("pilot"):
            _zip_writestr_deterministic(
                zf,
                "PILOT_NOTICE.txt",
                b"PILOT DATA - Not a compliance claim. This export is for evaluation and pilot feedback only.\n",
            )

        # Stable file ordering for deterministic ZIP bytes.
        _zip_writestr_deterministic(zf, "mrv_summary.json", _json_bytes(payload["mrv_summary"]))
        _zip_writestr_deterministic(
            zf, "emission_factor_snapshot.json", _json_bytes(payload["emission_factor"])
        )
        _zip_writestr_deterministic(zf, "audit_trail.json", _json_bytes({"rows": payload["audit_trail"]}))
        _zip_writestr_deterministic(
            zf,
            "evidence_hashes.json",
            _json_bytes({"rows": payload["evidence_hashes"]}),
        )
        _zip_writestr_deterministic(zf, "meta.json", _json_bytes(payload["meta"]))

        if cert_bytes is not None:
            _zip_writestr_deterministic(zf, "mrv_certificate.pdf", cert_bytes)

    return ExportPackage(filename=filename, content_type="application/zip", data=buf.getvalue())
