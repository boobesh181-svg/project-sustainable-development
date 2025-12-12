from fastapi import APIRouter

router = APIRouter()


@router.post("/")
async def create_mrv() -> dict:
    # TODO: implement MRV report creation
    return {"status": "ok"}
