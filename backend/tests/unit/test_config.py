import pytest
from pydantic import ValidationError

from app.config import Settings


def make(**kwargs: object) -> Settings:
    return Settings(_env_file=None, **kwargs)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ENV", "JWT_SECRET", "DATABASE_URL", "JWT_TTL_MINUTES", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_dev_environment_starts_without_jwt_secret() -> None:
    settings = make(env="dev")

    assert settings.jwt_secret is None
    assert settings.jwt_ttl_minutes == 30
    assert settings.gemini_api_key is None


def test_non_dev_environment_refuses_to_start_without_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(env="production")


def test_non_dev_environment_accepts_a_long_jwt_secret() -> None:
    settings = make(env="production", jwt_secret="x" * 32)

    assert settings.jwt_secret == "x" * 32


def test_non_dev_environment_rejects_a_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(env="production", jwt_secret="short")


def test_settings_read_from_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/db")
    monkeypatch.setenv("JWT_TTL_MINUTES", "5")

    settings = make()

    assert settings.database_url == "postgresql+psycopg://u:p@h/db"
    assert settings.jwt_ttl_minutes == 5
