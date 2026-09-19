from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str
    database_url: str = "postgresql+asyncpg://hire:hire@localhost:5432/hire"

    updates_mode: Literal["polling", "webhook"] = "polling"
    public_url: str = ""
    webhook_secret: str = ""

    max_api_url: str = "https://platform-api2.max.ru"
    max_api_timeout: float = 10.0
    # Сертификат API MAX выдан Russian Trusted Root CA, которого нет в certifi.
    max_extra_ca_file: Path = BASE_DIR / "certs" / "russian_trusted_root_ca.pem"
    # Ник бота для ссылок-приглашений; если пусто — берётся из GET /me при старте.
    bot_username: str = ""

    init_data_ttl_seconds: int = 24 * 3600
    webapp_dist: Path = BASE_DIR / "webapp" / "dist"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _check_webhook(self) -> "Settings":
        if self.updates_mode == "webhook":
            if not self.public_url.startswith("https://"):
                raise ValueError("UPDATES_MODE=webhook требует PUBLIC_URL вида https://...")
            if not self.webhook_secret:
                raise ValueError("UPDATES_MODE=webhook требует WEBHOOK_SECRET")
        self.public_url = self.public_url.rstrip("/")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
