from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uuid

from app.core.config import settings
from app.api.v1 import (
    auth,
    users,
    projects,
    tokens,
    demo,
    public,
    anomalies,
    dashboard,
    upload,
    evidence,
    emission_factors,
    material_tokens,
    deliveries,
    mrv_approval,
    anomaly_detection,
    audit_logs,
    mrv_company,
    mrv_export,
)
from app.db.session import init_db
from app.core.audit_context import set_audit_request_context


def _demo_write_locked_response() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "detail": "Demo mode: This action is disabled in DEMO mode",
        },
        headers={"Cache-Control": "no-store"},
    )

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """Async context manager for app startup/shutdown."""
    # Startup
    await init_db()

    # Demo mode auto-seeding (must succeed; no silent fallbacks)
    if settings.DEMO_MODE:
        from app.db.session import AsyncSessionLocal
        from app.services.demo_seed_service import ensure_demo_seeded

        async with AsyncSessionLocal() as db:
            await ensure_demo_seeded(db)
        logger.info("DEMO_MODE enabled: demo data ensured")

    yield
    # Shutdown (cleanup would go here if needed)


app = FastAPI(
    title="Sustainable Infrastructure Dashboard API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_request_context_middleware(request: Request, call_next):
    request_id = uuid.uuid4()
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    set_audit_request_context(
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return await call_next(request)


@app.middleware("http")
async def demo_mode_write_lock_middleware(request: Request, call_next):
    """Block destructive endpoints when DEMO_MODE is enabled.

    This does NOT change any business logic; it adds a safety guard so demo users
    cannot mutate compliance-relevant records.

    Enforcement of compliance-sensitive actions happens in the service layer.
    In DEMO mode, the demo must remain safe and non-destructive. We therefore
    block all write-like methods by default (POST/PUT/PATCH/DELETE) and allow
    only a narrow set of demo-safe interactions.
    """

    if not settings.DEMO_MODE:
        return await call_next(request)

    method = request.method.upper()

    if method in ("POST", "PUT", "PATCH", "DELETE"):
        path = request.url.path

        # Allow authentication flows (login/refresh/logout) so demo users can sign in.
        if path.startswith("/api/v1/auth/"):
            return await call_next(request)

        # Allow sandboxed evidence uploads only.
        if path.startswith("/api/v1/upload/evidence"):
            return await call_next(request)

        # Allow anomaly checks (read-only in DEMO_MODE).
        if path.startswith("/api/v1/anomalies/run/"):
            return await call_next(request)

        return _demo_write_locked_response()

    return await call_next(request)


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
    return {
        "status": "ok",
        "db": db_ok,
        "mode": "demo" if settings.DEMO_MODE else "prod",
    }


# Core API v1 routers (with /api/v1 prefix)
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(tokens.router, prefix="/api/v1/tokens", tags=["tokens"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(demo.router, prefix="/api/v1/demo", tags=["demo"])
app.include_router(public.router, prefix="/api/v1/public", tags=["public"])
app.include_router(anomalies.router, prefix="/api/v1/alerts", tags=["anomalies"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["upload"])
app.include_router(evidence.router)

# Module routers (prefix already defined in router)
app.include_router(emission_factors.router)
app.include_router(material_tokens.router)
app.include_router(deliveries.router)
app.include_router(mrv_approval.router)
app.include_router(anomaly_detection.router)
app.include_router(audit_logs.router)
app.include_router(mrv_company.router)
app.include_router(mrv_export.router)

# Legacy MRV router (guarded import)
try:
    from app.api.v1 import mrv

    app.include_router(mrv.router, prefix="/mrv", tags=["mrv"])
    logger.info("MRV router included successfully")
except Exception as e:
    import traceback

    logger.exception("Failed to include MRV router: %s", e)
    traceback.print_exc()

# MRV ingestion router (legacy, not canonical) - disabled by default.
if settings.ENABLE_MRV_INGESTION:
    try:
        from app.mrv.routes import router as mrv_ingestion_router

        app.include_router(mrv_ingestion_router, tags=["mrv-ingestion"])
        logger.info("MRV ingestion router included successfully")
    except Exception as e:
        import traceback

        logger.exception("Failed to include MRV ingestion router: %s", e)
        traceback.print_exc()

