from functools import lru_cache
from pathlib import Path
from typing import ClassVar, List

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=str(_BACKEND_ROOT / ".env"), override=False)


class Settings(BaseSettings):
    """Application settings loaded from environment (.env).

    Secrets like SECRET_KEY and DATABASE_URL must be provided via environment
    or a local .env file (see .env.example).
    """

    _BACKEND_ROOT: ClassVar[Path] = _BACKEND_ROOT

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ENV: str = Field("local", description="Runtime environment name")

    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    GRID_EMISSION_FACTOR: float = 0.82

    CORS_ORIGINS: List[AnyHttpUrl] | List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8001",
        ],
        description="Allowed CORS origins",
    )

    SENTRY_DSN: str | None = None

    # Uploads
    UPLOAD_ROOT: str = str(_BACKEND_ROOT / "uploads")

    # Demo uploads (sandbox)
    DEMO_UPLOAD_ROOT: str = Field(
        str(_BACKEND_ROOT / "demo_uploads"),
        description="Storage root for sandboxed demo evidence when DEMO_MODE=true",
    )

    # Feature gates (default OFF for regulator-grade MRV mode)
    ENABLE_MRV_INGESTION: bool = Field(
        False,
        description="Enable MRV ingestion routes under /api/mrv/* (can be disabled in hardened deployments)",
    )
    ENABLE_CARBON_CREDITS: bool = Field(
        False,
        description="Enable any carbon-credit issuance/retirement APIs (default disabled)",
    )

    # Demo mode (LOI pilot safety)
    DEMO_MODE: bool = Field(
        False,
        description=(
            "When true, the system runs in a safe demo posture: seeds synthetic demo data, "
            "blocks destructive endpoints, and watermarks exports as DEMO."
        ),
    )


# Default carbon factor mappings; can be overridden via DB or config table.
CARBON_FACTORS_BASELINE = {
    "cement": 0.9,  # kg CO2 per kg material (example placeholder)
    "recycled_cement": 0.5,
    "steel": 1.9,
}

CARBON_FACTORS_GREEN = {
    "cement": 0.6,
    "recycled_cement": 0.2,
    "steel": 1.4,
}


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
