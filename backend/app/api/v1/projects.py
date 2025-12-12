from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_projects() -> list[dict]:
    # TODO: implement real project listing with role scoping
    return []


@router.get("/{project_id}")
async def get_project(project_id: str) -> dict:
    # TODO: implement real project retrieval
    return {"id": project_id}


@router.post("/")
async def create_project() -> dict:
    # TODO: implement real project creation with role checks
    return {"status": "created"}
