from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_tokens() -> list[dict]:
    # TODO: implement material token listing
    return []
