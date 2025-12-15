from functools import lru_cache
from typing import List

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment (.env).

    Secrets like SECRET_KEY and DATABASE_URL must be provided via environment
    or a local .env file (see .env.example).
    """

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    ENV: str = Field("local", description="Runtime environment name")

    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"

    GRID_EMISSION_FACTOR: float = 0.82

    CORS_ORIGINS: List[AnyHttpUrl] | List[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins",
    )

    SENTRY_DSN: str | None = None

    # Uploads
    UPLOAD_ROOT: str = "./uploads"


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
