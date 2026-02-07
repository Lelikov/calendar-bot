from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLevelNamesMapping

import sentry_sdk
import structlog
from dishka import make_async_container
from dishka.integrations.aiogram import AiogramProvider
from dishka.integrations.aiogram import setup_dishka as setup_aiogram_dishka
from dishka.integrations.fastapi import FastapiProvider, setup_dishka
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config.logger import setup_logger
from app.handlers import messages  # noqa: F401
from app.interfaces.telegram import ITelegramController
from app.ioc import AppProvider, dp
from app.routes import root_router
from app.settings import Settings


logger = structlog.get_logger(__name__)


container = make_async_container(AppProvider(), FastapiProvider(), AiogramProvider())


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    settings = await container.get(Settings)
    log_level = getLevelNamesMapping().get(settings.log_level)
    setup_logger(log_level=log_level, console_render=settings.debug)

    if settings.sentry_dsn:
        logger.info(f"Initializing Sentry with DSN: {settings.sentry_dsn}")
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            send_default_pii=True,
            environment="dev" if settings.debug else "production",
            debug=settings.debug,
        )

    logger.info("🚀 Starting application")
    engine = await container.get(AsyncEngine)
    telegram_controller = await container.get(ITelegramController)
    await telegram_controller.start()
    yield
    await engine.dispose()
    logger.info("⛔ Stopping application")


app = FastAPI(lifespan=lifespan)
setup_aiogram_dishka(container=container, router=dp, auto_inject=True)
setup_dishka(container, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.error("Validation error", path=request.url.path, errors=exc.errors(), body=exc.body)
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


app.include_router(root_router)
