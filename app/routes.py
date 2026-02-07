import hashlib
import hmac
from typing import Annotated

import jwt
import structlog
from aiogram import Bot, types
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Header, HTTPException, status
from starlette.requests import Request

from app.interfaces.booking import IBookingController
from app.interfaces.mail import IMailWebhookController
from app.interfaces.meeting import IMeetWebhookController
from app.ioc import dp
from app.schemas import BookingEvent, BookingReminderBody, JitsiWebhookEvent, MailWebhookEvent
from app.settings import Settings


logger = structlog.get_logger(__name__)

root_router = APIRouter(
    prefix="",
    tags=["root"],
    responses={404: {"description": "Not found"}},
    route_class=DishkaRoute,
)


async def validate_signature(signature: str, request: Request) -> bool:
    body = await request.body()
    settings: Settings = request.app.state.dishka_container.get(Settings)
    return signature == hmac.new(settings.cal_signature.encode(), body, hashlib.sha256).hexdigest()


@root_router.post("/booking/reminder", status_code=status.HTTP_201_CREATED)
async def booking_reminder(
    booking_controller: FromDishka[IBookingController],
    settings: FromDishka[Settings],
    body: BookingReminderBody | None = None,
    admin_api_token: Annotated[str | None, Header(alias="admin-api-token")] = None,
) -> int:
    if admin_api_token != settings.admin_api_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    if not body:
        body = BookingReminderBody()
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
    settings: FromDishka[Settings],
    booking_controller: FromDishka[IBookingController],
) -> None:
    if not settings.debug and not await validate_signature(signature=signature, request=request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature validation error")
    request_body = await request.json()
    logger.info(f"Received booking event {request_body}")
    await booking_controller.handle_booking(booking_event.to_dto())
    return None


@root_router.post("/mail/webhook")
async def mail_webhook(
    event: MailWebhookEvent,
    mail_controller: FromDishka[IMailWebhookController],
) -> None:
    logger.info(event)
    await mail_controller.handle_webhook(event.to_dto())
    return None


@root_router.post("/telegram")
async def bot_webhook(
    update: dict,
    bot: FromDishka[Bot],
    settings: FromDishka[Settings],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> None | dict:
    if x_telegram_bot_api_secret_token != settings.telegram_my_token:
        logger.error("Wrong secret token !")
        return {"status": "error", "message": "Wrong secret token !"}
    telegram_update = types.Update(**update)
    await dp.feed_webhook_update(bot=bot, update=telegram_update)
    return None


@root_router.post("/jitsi/webhook")
async def jitsi_webhook(
    event: JitsiWebhookEvent,
    meet_controller: FromDishka[IMeetWebhookController],
    settings: FromDishka[Settings],
) -> None:
    try:
        jwt.decode(
            event.jwt,
            settings.jitsi_jwt_token,
            algorithms=["HS256"],
            audience=settings.meeting_jwt_aud,
            issuer=settings.meeting_jwt_iss,
        )
    except jwt.PyJWTError as e:
        logger.exception("Jitsi webhook JWT validation error")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="JWT validation error") from e

    await meet_controller.handle_webhook(event.to_dto())
    return None
