from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (prefix SDT_)."""

    model_config = SettingsConfigDict(env_prefix="SDT_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "staging", "prod"] = "dev"
    database_url: str = "postgresql+psycopg://sdtreasury:sdtreasury@localhost:5432/sdtreasury"

    # Auth: "dev" issues local HS256 tokens (never enabled outside dev/test);
    # "cognito" validates RS256 tokens against the Cognito user pool JWKS.
    auth_mode: Literal["dev", "cognito"] = "dev"
    dev_jwt_secret: str = "dev-only-insecure-secret-change-me-0000"
    cognito_region: str = "eu-south-2"
    cognito_user_pool_id: str = ""
    cognito_app_client_id: str = ""

    cors_origins: list[str] = ["http://localhost:5173"]

    odoo_timeout_seconds: float = 60.0
    odoo_page_size: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()
