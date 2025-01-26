from functools import lru_cache
from typing import final

from pydantic import Field
from pydantic_settings import BaseSettings


@final
class Settings(BaseSettings):
    debug: bool = False
    log_level: str = "DEBUG"
    redis_url: str = "redis://localhost:6379/0"
    bot_token: str
    base_webhook_url: str
    webhook_path: str = "/telegram"
    telegram_my_token: str
    is_check_first_run: bool = False
    postgres_dsn: str = Field(strict=True)
    cal_signature: str = Field(strict=True)
    openai_api_key: str = Field(strict=True)


@lru_cache  # get it from memory
def get_settings() -> Settings:
    return Settings()
