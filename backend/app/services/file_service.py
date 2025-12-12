import os
from pathlib import Path
from typing import Literal

from fastapi import UploadFile

from app.core.config import settings

UploadType = Literal["evidence", "mrv", "whistleblower"]


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
