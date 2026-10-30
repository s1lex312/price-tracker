"""Application configuration via environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, overridable through env vars or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "sqlite+aiosqlite:///./price_tracker.db"
    postgres_user: str = "pricetracker"
    postgres_password: str = "change_me"
    postgres_db: str = "pricetracker"

    alert_bot_token: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    alert_email_to: str = ""

    secret_key: str = "dev-secret-change-me"

    auth_enabled: bool = True
    demo_user_id: int = 0

    scheduler_interval_minutes: int = 180
    alert_cooldown_hours: int = 24
    redis_url: str = "redis://localhost:6379/0"

    environment: str = "development"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
