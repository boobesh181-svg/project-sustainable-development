from fastapi import APIRouter, UploadFile, File

from app.services.file_service import save_upload, UploadType

router = APIRouter()


@router.post("/{upload_type}")
async def upload_file(
    upload_type: UploadType,
    file: UploadFile = File(...),
) -> dict:
    path = await save_upload(file, upload_type)
    return {"path": path}
