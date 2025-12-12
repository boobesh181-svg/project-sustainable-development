# app/api/v1/mrv_test.py - temporary minimal test
from fastapi import APIRouter, HTTPException

router = APIRouter()

@router.get("/ping")
def ping():
    return {"ok": True, "router": "mrv", "msg": "pong"}

# temporary basic stats endpoint WITHOUT response_model for isolation
@router.get("/stats")
def stats():
    # return a safe JSON object that does not require pydantic parsing
    return {"projects": 0, "reports": 0, "notes": "temporary stats endpoint"}
