import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://appuser:apppassword@localhost:5432/appdb")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "CHANGE_ME")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
    GRID_EMISSION_FACTOR: float = float(os.getenv("GRID_EMISSION_FACTOR", "0.82"))
    UPLOADS_DIR: str = os.getenv("UPLOADS_DIR", "/data/uploads")

settings = Settings()
