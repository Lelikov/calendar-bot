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
from app.controllers.mail import MailController
from app.schemas import BookingEvent, BookingReminderBody, MailWebhookEvent
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


def get_mail_controller() -> MailController:
    return MailController(bot=bot, settings=cfg)


@root_router.post("/booking/reminder", status_code=status.HTTP_201_CREATED)
async def booking_reminder(
    body: BookingReminderBody,
    booking_controller: Annotated[BookingController, Depends(get_booking_controller)],
    admin_api_token: Annotated[str | None, Header(alias="admin-api-token")] = None,
) -> int:
    if admin_api_token != cfg.admin_api_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    count_sent_reminders = await booking_controller.handle_booking_reminder(
        start_time_from_shift=body.start_time_from_shift,
        start_time_to_shift=body.start_time_to_shift,
    )
    logger.info(f"Sent {count_sent_reminders} reminders")
    return count_sent_reminders


@root_router.post("/booking")
async def booking(
    booking_event: BookingEvent,
    request: Request,
    signature: Annotated[str | None, Header(alias="x-cal-signature-256")],
    booking_controller: Annotated[BookingController, Depends(get_booking_controller)],
) -> None:
    if not cfg.debug and not await validate_signature(signature=signature, request=request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature validation error")
    request_body = await request.json()
    logger.info(f"Received booking event {request_body}")
    await booking_controller.handle_booking(booking_event.to_dto())
    return None


@root_router.post("/mail/webhook")
async def mail_webhook(
    event: MailWebhookEvent,
    mail_controller: Annotated[MailController, Depends(get_mail_controller)],
) -> None:
    logger.info(event)
    await mail_controller.handle_webhook(event.to_dto())
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
