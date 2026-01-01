from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Literal

from fastapi import UploadFile

from app.core.config import settings

UploadType = Literal["evidence", "mrv", "whistleblower"]


def sha256_bytes(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


async def save_upload_with_hash(file: UploadFile, upload_type: UploadType, *, demo: bool = False) -> dict:
    if is_forbidden_extension(file.filename):
        raise ValueError("Forbidden file type")

    if demo and not settings.DEMO_MODE:
        raise ValueError("Demo uploads are only allowed when DEMO_MODE=true")

    safe_name = sanitize_filename(file.filename)

    # Demo evidence is sandboxed to a dedicated root directory.
    base_root = Path(settings.DEMO_UPLOAD_ROOT) if demo else Path(settings.UPLOAD_ROOT)
    target_dir = base_root / upload_type
    target_dir.mkdir(parents=True, exist_ok=True)

    # Lightweight watermarking for demo evidence: prefix filename so the artifact
    # is obviously non-production if it is ever copied elsewhere.
    stored_name = safe_name
    if demo and upload_type == "evidence" and not stored_name.upper().startswith("DEMO_"):
        stored_name = f"DEMO_{stored_name}"

    target_path = target_dir / stored_name

    contents = await file.read()
    target_path.write_bytes(contents)

    watermark_path: str | None = None
    if demo and upload_type == "evidence":
        watermark_path_obj = target_dir / f"{stored_name}.watermark.txt"
        watermark_path_obj.write_text(
            "DEMO MODE - No real compliance claims. Evidence is sandboxed and not valid for production MRV.\n",
            encoding="utf-8",
        )
        watermark_path = str(watermark_path_obj)

    return {
        "path": str(target_path),
        "sha256": sha256_bytes(contents),
        "size_bytes": len(contents),
        "content_type": getattr(file, "content_type", None),
        "original_filename": file.filename,
        "watermark_path": watermark_path,
    }


def sanitize_filename(filename: str) -> str:
    # Very small subset of secure_filename behaviour
    keepchars = (".", "_", "-")
    clean = "".join(c for c in filename if c.isalnum() or c in keepchars).strip("._")
    if not clean:
        clean = "file"
    return clean


def is_forbidden_extension(filename: str) -> bool:
    forbidden = {".exe", ".sh", ".bat", ".cmd"}
    ext = os.path.splitext(filename)[1].lower()
    return ext in forbidden


async def save_upload(file: UploadFile, upload_type: UploadType) -> str:
    if is_forbidden_extension(file.filename):
        raise ValueError("Forbidden file type")

    safe_name = sanitize_filename(file.filename)
    target_dir = Path(settings.UPLOAD_ROOT) / upload_type
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name

    contents = await file.read()
    target_path.write_bytes(contents)

    # Return path relative to app root for serving later
    return str(target_path)
