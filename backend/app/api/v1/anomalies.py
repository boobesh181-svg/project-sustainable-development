from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def create_anomaly() -> dict:
    # TODO: implement anomaly creation and ML scoring
    return {"status": "ok"}
