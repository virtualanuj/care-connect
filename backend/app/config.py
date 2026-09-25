from functools import lru_cache
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Application configuration, read from environment variables only."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://careconnect:careconnect@localhost:5432/careconnect"
    jwt_secret: str | None = None
    jwt_ttl_minutes: int = 30
    gemini_api_key: str | None = None
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None

    @model_validator(mode="after")
    def _require_jwt_secret_outside_dev(self) -> Self:
        if self.env != "dev" and (
            self.jwt_secret is None or len(self.jwt_secret) < MIN_JWT_SECRET_LENGTH
        ):
            raise ValueError(f"JWT_SECRET (at least {MIN_JWT_SECRET_LENGTH} chars) is required")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
