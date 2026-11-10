from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-only-insecure-secret-change-me-0000"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (prefix SDT_)."""

    model_config = SettingsConfigDict(env_prefix="SDT_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://sdtreasury:sdtreasury@localhost:5432/sdtreasury"

    # Platform-issued JWTs (HS256). MUST be overridden outside dev/test (checked at startup).
    jwt_secret: str = DEV_JWT_SECRET
    jwt_ttl_hours: int = 10

    cors_origins: list[str] = ["http://localhost:5173"]

    odoo_timeout_seconds: float = 60.0
    odoo_page_size: int = 500

    # Scheduler (MVP: a simple loop instead of SQS/EventBridge).
    sync_interval_seconds: int = 900

    @property
    def dev_login_enabled(self) -> bool:
        return self.env in ("dev", "test")

    def check_production_safety(self) -> None:
        if self.env in ("staging", "prod") and (
            self.jwt_secret == DEV_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise RuntimeError("SDT_JWT_SECRET must be set (32+ chars) outside dev/test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
