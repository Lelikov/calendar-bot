from contextlib import asynccontextmanager
from logging import getLevelNamesMapping

import ngrok
import structlog
from fastapi import FastAPI

from config.logger import setup_logger
from routes import root_router
from settings import get_settings


logger = structlog.get_logger(__name__)

cfg = get_settings()


async def create_listener():
    session = await ngrok.SessionBuilder().authtoken_from_env().connect()
    listener = await session.http_endpoint().listen()
    listener.forward("localhost:8000")
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
    from bot import start_telegram

    await start_telegram(base_webhook_url=base_webhook_url)
    yield
    logger.info("⛔ Stopping application")
    ngrok.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(root_router)
