import hashlib
import hmac
from typing import Annotated

import structlog
from aiogram import types
from fastapi import APIRouter, Depends, Header, HTTPException, status
from starlette.requests import Request

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.bot import bot, dp
from app.controllers.booking import BookingController
from app.schemas import BookingEvent
from app.settings import get_settings


logger = structlog.get_logger(__name__)


cfg = get_settings()

root_router = APIRouter(
    prefix="",
    tags=["root"],
    responses={404: {"description": "Not found"}},
)


async def validate_signature(signature: str, request: Request) -> bool:
    body = await request.body()
    return signature == hmac.new(cfg.cal_signature.encode(), body, hashlib.sha256).hexdigest()


def get_booking_controller() -> BookingController:
    return BookingController(
        db=BookingDatabaseAdapter(cfg.postgres_dsn),
        shortener=UrlShortenerAdapter(),
        bot=bot,
    )


@root_router.post("/booking")
async def booking(
    booking_event: BookingEvent,
    request: Request,
    signature: Annotated[str | None, Header(alias="x-cal-signature-256")],
    booking_controller: Annotated[BookingController, Depends(get_booking_controller)],
) -> None:
    if not cfg.debug and not await validate_signature(signature=signature, request=request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature validation error")

    await booking_controller.handle_booking(booking_event)
    return None


@root_router.post(cfg.webhook_path)
async def bot_webhook(
    update: dict,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> None | dict:
    if x_telegram_bot_api_secret_token != cfg.telegram_my_token:
        logger.error("Wrong secret token !")
        return {"status": "error", "message": "Wrong secret token !"}
    telegram_update = types.Update(**update)
    await dp.feed_webhook_update(bot=bot, update=telegram_update)
    return None
