"""Environment configuration (01-architecture §5).

Every process reads its environment through :func:`get_env`. Values that the owner
enters in the UI (Google, Notion, LLM, VAPID, Discord) may stay empty in the
environment; those are stored encrypted in ``app_setting`` instead (D-18).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env lives at the repo root, one level above backend/.
_REPO_ROOT = Path(__file__).resolve().parents[3]

EnvName = Literal["dev", "test", "prod"]


class Env(BaseSettings):
    """Typed view of the process environment."""

    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- core (required in prod) ---
    APP_ENV: EnvName = "dev"
    APP_BASE_URL: str = "http://localhost:3000"
    APP_ENCRYPTION_KEY: str = ""
    APP_SESSION_SECRET: str = ""
    OWNER_EMAIL: str = ""

    # --- database ---
    DATABASE_URL: str = "postgresql+psycopg://tartib:tartib@localhost:5433/tartib"
    TEST_DATABASE_URL: str = "postgresql+psycopg://tartib:tartib@localhost:5433/tartib_test"
    POSTGRES_PASSWORD: str = "tartib"

    # --- hosting / URLs ---
    API_HOST: str = "localhost"
    API_PUBLIC_URL: str = "http://localhost:8000"
    API_ORIGIN: str = ""

    # --- optional integrations (may be set in the UI instead) ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    NOTION_TOKEN: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com"
    LLM_MODEL: str = "deepseek-chat"
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_SUBJECT: str = "mailto:owner@example.com"
    DISCORD_ALERT_WEBHOOK_URL: str = ""
    HEALTHCHECK_PING_URL: str = ""

    # --- email ---
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "tartib@localhost"

    # --- behaviour switches ---
    FAKE_GOOGLE: bool = Field(default=True, description="1 → in-memory Google Calendar")

    @property
    def is_prod(self) -> bool:
        return self.APP_ENV == "prod"

    @model_validator(mode="after")
    def _require_secrets_in_prod(self) -> Env:
        """Fail fast instead of booting production with blank secrets."""
        if not self.is_prod:
            return self
        missing = [
            name
            for name in (
                "APP_BASE_URL",
                "APP_ENCRYPTION_KEY",
                "APP_SESSION_SECRET",
                "OWNER_EMAIL",
                "DATABASE_URL",
                "POSTGRES_PASSWORD",
            )
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"APP_ENV=prod requires: {', '.join(sorted(missing))}")
        return self


@lru_cache(maxsize=1)
def get_env() -> Env:
    """Process-wide cached environment."""
    return Env()


def reset_env_cache() -> None:
    """Drop the cache (tests that mutate os.environ)."""
    get_env.cache_clear()
