from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLevelNamesMapping

import sentry_sdk
import structlog
from databases import Database
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.logger import setup_logger
from app.controllers.telegram import TelegramController
from app.di import container
from app.handlers import messages  # noqa: F401
from app.routes import root_router
from app.settings import Settings


logger = structlog.get_logger(__name__)


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
    database = await container.get(Database)
    await database.connect()
    telegram_controller = await container.get(TelegramController)
    await telegram_controller.start()
    yield
    await database.disconnect()
    logger.info("⛔ Stopping application")


app = FastAPI(lifespan=lifespan)
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
