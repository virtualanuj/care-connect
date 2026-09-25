from functools import lru_cache
from typing import Literal, Self

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
    gemini_model: str = "gemini-2.0-flash"
    # "fake" / "fake-down" are development stand-ins (deterministic, no network); dev only.
    llm_provider: Literal["gemini", "fake", "fake-down"] = "gemini"
    default_phone_region: str = "IN"
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None

    @model_validator(mode="after")
    def _no_fake_ai_outside_dev(self) -> Self:
        if self.env != "dev" and self.llm_provider != "gemini":
            raise ValueError("LLM_PROVIDER fake modes are only allowed when ENV=dev")
        return self

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
