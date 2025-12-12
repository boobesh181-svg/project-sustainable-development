from fastapi import APIRouter

router = APIRouter(tags=["mrv"])

@router.get("/health")
def health():
    return {"status":"ok","msg":"mrv healthy"}

@router.get("/stats-simple")
def stats_simple():
    return {"projects":0,"reports":0}
