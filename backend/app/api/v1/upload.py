from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.evidence import Evidence
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        saved = await save_upload_with_hash(file, upload_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    evidence = Evidence(
        upload_type=str(upload_type),
        storage_path=saved["path"],
        sha256=saved["sha256"],
        size_bytes=int(saved["size_bytes"]),
        content_type=saved.get("content_type"),
        original_filename=saved.get("original_filename"),
        created_by=current_user.id,
        report_id=report_id,
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
            "sha256": saved["sha256"],
            "size_bytes": int(saved["size_bytes"]),
            "storage_path": saved["path"],
            "original_filename": saved.get("original_filename"),
            "content_type": saved.get("content_type"),
            "report_id": str(report_id) if report_id else None,
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
