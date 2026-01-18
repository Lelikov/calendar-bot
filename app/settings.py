from functools import lru_cache
from typing import final

from pydantic import Field
from pydantic_settings import BaseSettings


@final
class Settings(BaseSettings):
    base_webhook_url: str
    booking_host_url: str = "localhost:3000"
    bot_token: str
    cal_signature: str = Field(strict=True)
    debug: bool = False
    is_check_first_run: bool = False
    jitsi_jwt_token: str = Field(strict=True)
    log_level: str = "DEBUG"
    meeting_host_url: str = "localhost:8080"
    meeting_jwt_aud: str
    meeting_jwt_iss: str
    openai_api_key: str = Field(strict=True, default="")
    postgres_dsn: str = Field(strict=True)
    redis_url: str = "redis://localhost:6379/0"
    sentry_dsn: str | None = Field(strict=True, default=None)
    shortify_api_key: str | None = Field(strict=True, default=None)
    shortner_url: str
    from_email: str
    from_email_name: str
    email_api_url: str
    email_api_key: str = Field(strict=True)
    smtp_host: str | None = Field(strict=True, default=None)
    smtp_port: int | None = Field(strict=True, default=2525)
    smtp_user: str | None = Field(strict=True, default=None)
    smtp_password: str | None = Field(strict=True, default=None)
    support_email: str = "info@localhost.local"
    telegram_my_token: str
    webhook_path: str = "/telegram"
    admin_chat_ids: list[int] = Field(default_factory=list)
    admin_api_token: str = Field(strict=True)

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache  # get it from memory
def get_settings() -> Settings:
    return Settings()
