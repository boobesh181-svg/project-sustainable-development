from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.models.evidence import Evidence
from app.models.material_token import MaterialToken
from app.models.mrv_report import MRVReport
from app.models.role import RoleName
from app.services.audit_log_service import write_audit_log
from app.services.file_service import save_upload_with_hash, UploadType

router = APIRouter()


@router.post("/{upload_type}")
async def upload_file(
    upload_type: UploadType,
    request: Request,
    file: UploadFile = File(...),
    report_id: UUID | None = Query(
        None,
        description="Optional MRV report to attach this evidence to",
    ),
    token_uid: str | None = Query(
        None,
        description="Optional material token UID to attach this evidence to (supplier portal)",
    ),
    evidence_kind: str | None = Query(
        None,
        description="Optional logical type: epd | invoice | other (stored as Evidence.upload_type when upload_type=evidence)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    # Demo-mode sandboxing: allow evidence uploads only when they attach to a DEMO project.
    # This keeps demo uploads isolated from compliance-relevant records.
    demo_project_ok = True
    if settings.DEMO_MODE:
        if str(upload_type) != "evidence":
            raise HTTPException(status_code=423, detail="Demo mode: only evidence uploads are allowed")
        if report_id is None and token_uid is None:
            raise HTTPException(
                status_code=400,
                detail="Demo mode: report_id or token_uid is required for evidence uploads",
            )
        demo_project_ok = False

    material_token_id = None
    if token_uid is not None:
        token = (
            await db.execute(
                select(MaterialToken)
                .options(
                    selectinload(MaterialToken.delivery_verification),
                    selectinload(MaterialToken.project),
                )
                .where(MaterialToken.token_uid == token_uid)
            )
        ).scalar_one_or_none()
        if token is None:
            raise HTTPException(status_code=404, detail="Material token not found")

        if settings.DEMO_MODE:
            if getattr(token, "project", None) is not None and str(token.project.name).upper().startswith("DEMO"):
                demo_project_ok = True

        # Supplier-scoped enforcement: suppliers can only attach evidence to their own tokens.
        if current_user.role is None:
            raise HTTPException(status_code=403, detail="Not authorized")
        if current_user.role.name == RoleName.SUPPLIER:
            supplier_name = current_user.supplier.name if getattr(current_user, "supplier", None) else None
            if supplier_name is None:
                raise HTTPException(status_code=403, detail="Supplier scope not configured")
            if token.supplier_name != supplier_name:
                raise HTTPException(status_code=403, detail="Not authorized for this supplier")
            # Do not allow new uploads after delivery verification is locked.
            if getattr(token, "delivery_verification", None) is not None and token.delivery_verification.is_verified:
                raise HTTPException(status_code=409, detail="Token delivery is already verified; evidence is locked")

        material_token_id = token.id

    if report_id is not None and settings.DEMO_MODE:
        report = (
            await db.execute(
                select(MRVReport)
                .options(selectinload(MRVReport.project))
                .where(MRVReport.id == report_id)
            )
        ).scalar_one_or_none()
        if report is None:
            raise HTTPException(status_code=404, detail="MRV report not found")
        if getattr(report, "project", None) is not None and str(report.project.name).upper().startswith("DEMO"):
            demo_project_ok = True

    if settings.DEMO_MODE and not demo_project_ok:
        raise HTTPException(status_code=403, detail="Demo mode: uploads are allowed only for DEMO projects")

    try:
        saved = await save_upload_with_hash(file, upload_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    logical_upload_type = str(upload_type)
    if str(upload_type) == "evidence" and evidence_kind:
        logical_upload_type = evidence_kind

    evidence = Evidence(
        upload_type=logical_upload_type,
        storage_path=saved["path"],
        sha256=saved["sha256"],
        size_bytes=int(saved["size_bytes"]),
        content_type=saved.get("content_type"),
        original_filename=saved.get("original_filename"),
        created_by=current_user.id,
        report_id=report_id,
        material_token_id=material_token_id,
        demo_only=bool(settings.DEMO_MODE),
        non_compliant=bool(settings.DEMO_MODE),
    )
    db.add(evidence)
    await db.commit()
    await db.refresh(evidence)

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    await write_audit_log(
        db=db,
        actor=current_user.email,
        actor_user_id=current_user.id,
        action="EVIDENCE_UPLOADED",
        entity_type="Evidence",
        entity_id=str(evidence.id),
        event_payload={
            "upload_type": str(upload_type),
            "evidence_kind": evidence_kind,
            "sha256": saved["sha256"],
            "size_bytes": int(saved["size_bytes"]),
            "storage_path": saved["path"],
            "original_filename": saved.get("original_filename"),
            "content_type": saved.get("content_type"),
            "report_id": str(report_id) if report_id else None,
            "token_uid": token_uid,
            "demo_mode": bool(settings.DEMO_MODE),
            "demo_only": bool(settings.DEMO_MODE),
            "non_compliant": bool(settings.DEMO_MODE),
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )

    return {
        "path": saved["path"],
        "sha256": saved["sha256"],
        "size_bytes": int(saved["size_bytes"]),
        "evidence_id": str(evidence.id),
    }
