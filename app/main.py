from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from logging import getLevelNamesMapping

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import handlers  # noqa: F401
from app.config.logger import setup_logger
from app.routes import root_router
from app.settings import get_settings


logger = structlog.get_logger(__name__)

cfg = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    log_level = getLevelNamesMapping().get(cfg.log_level)
    setup_logger(log_level=log_level, console_render=cfg.debug)

    logger.info("🚀 Starting application")
    from app.bot import start_telegram  # noqa: PLC0415

    await start_telegram(base_webhook_url=cfg.base_webhook_url)
    yield
    logger.info("⛔ Stopping application")


if cfg.sentry_dsn:
    logger.info(f"Initializing Sentry with DSN: {cfg.sentry_dsn}")
    sentry_sdk.init(
        dsn=cfg.sentry_dsn,
        send_default_pii=True,
        environment="dev" if cfg.debug else "production",
        debug=cfg.debug,
    )

app = FastAPI(lifespan=lifespan)

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
