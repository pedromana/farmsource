from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Farmsource"
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    database_url: str = Field(
        default="sqlite:///./data/farmsource.db",
        validation_alias="DATABASE_URL",
    )
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    stripe_secret_key: str | None = Field(default=None, validation_alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str | None = Field(default=None, validation_alias="STRIPE_PUBLISHABLE_KEY")
    app_base_url: str = Field(default="http://127.0.0.1:8000", validation_alias="APP_BASE_URL")
    session_secret_key: str = Field(default="change-this-local-secret", validation_alias="SESSION_SECRET_KEY")
    admin_default_email: str = Field(default="admin@farmsource.local", validation_alias="ADMIN_DEFAULT_EMAIL")
    admin_default_password: str = Field(default="ChangeMe123!", validation_alias="ADMIN_DEFAULT_PASSWORD")

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
