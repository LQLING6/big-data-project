import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./campuscomp.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    cors_origins: tuple[str, ...] = tuple(
        os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    )


settings = Settings()
