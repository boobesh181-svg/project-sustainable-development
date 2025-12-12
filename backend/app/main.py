from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.v1 import auth, users, projects, tokens, mrv, anomalies, dashboard, upload
from app.db.session import init_db

app = FastAPI(title="Sustainable Infrastructure Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup() -> None:
    await init_db()

@app.get("/health")
async def health() -> dict:
    from app.db.session import async_engine
    try:
        # simple DB connectivity check
        async with async_engine.begin() as conn:  # type: ignore[func-returns-value]
            await conn.run_sync(lambda _: None)
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok}

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tokens.router, prefix="/api/v1/tokens", tags=["tokens"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(mrv.router, prefix="/api/v1/mrv", tags=["mrv"])
app.include_router(anomalies.router, prefix="/api/v1/alerts", tags=["anomalies"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
