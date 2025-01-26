import os
from contextlib import asynccontextmanager
from logging import getLevelNamesMapping

import structlog
from fastapi import FastAPI

from app import handlers  # noqa: F401
from app.config.logger import setup_logger
from app.routes import root_router
from app.settings import get_settings


logger = structlog.get_logger(__name__)

cfg = get_settings()

if cfg.debug:
    import ngrok


async def create_listener():
    session = await ngrok.SessionBuilder().authtoken_from_env().connect()
    listener = await session.http_endpoint().domain(os.getenv("NGROK_DOMAIN")).listen()
    listener.forward(addr="127.0.0.1:8000")
    return listener


@asynccontextmanager
async def lifespan(application: FastAPI):
    log_level = getLevelNamesMapping().get(cfg.log_level)
    setup_logger(log_level=log_level, console_render=cfg.debug)

    base_webhook_url = cfg.base_webhook_url
    if cfg.debug:
        listener = await create_listener()
        base_webhook_url = listener.url()

    logger.info("🚀 Starting application")
    from app.bot import start_telegram

    await start_telegram(base_webhook_url=base_webhook_url)
    yield
    logger.info("⛔ Stopping application")
    if cfg.debug:
        ngrok.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(root_router)
