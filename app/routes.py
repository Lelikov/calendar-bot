import hashlib
import hmac
from enum import StrEnum
from typing import Annotated

import pytz
import structlog
from aiogram import types
from databases import Database
from dateutil import parser
from fastapi import APIRouter, Header, HTTPException, status
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic.alias_generators import to_camel
from starlette.requests import Request

from app.bot import bot, dp
from app.constant import OPENAI_CONTENT_TEMPLATE
from app.settings import get_settings


logger = structlog.get_logger(__name__)


cfg = get_settings()

root_router = APIRouter(
    prefix="",
    tags=["root"],
    responses={404: {"description": "Not found"}},
)


client = AsyncOpenAI(api_key=cfg.openai_api_key)


class BookingEventOrganizer(BaseModel):
    email: str
    time_zone: str

    class Config:
        alias_generator = to_camel


class BookingEventPayload(BaseModel):
    booking_id: int
    description: str | None
    end_time: str
    organizer: BookingEventOrganizer
    start_time: str
    title: str

    class Config:
        alias_generator = to_camel


class TriggerEvent(StrEnum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"


class BookingEvent(BaseModel):
    payload: BookingEventPayload
    trigger_event: TriggerEvent

    class Config:
        alias_generator = to_camel


async def get_organizer_chat_id(email: str):
    async with Database(cfg.postgres_dsn) as database:
        query = (
            "SELECT telegram_chat_id FROM users "
            "WHERE locked = FALSE "
            "AND email = :email "
            "AND telegram_chat_id IS NOT NULL"
        )
        row = await database.fetch_one(query=query, values={"email": email})
    if row:
        return row["telegram_chat_id"]
    return None


TIME_FORMAT = "%d-%m-%Y %H:%M"


async def validate_signature(signature: str, request: Request) -> bool:
    body = await request.body()
    return signature == hmac.new(cfg.cal_signature.encode(), body, hashlib.sha256).hexdigest()


def get_organizer_time(organizer_tz, start_time):
    return (
        parser.isoparse(start_time)
        .replace(tzinfo=pytz.utc)
        .astimezone(organizer_tz)
        .strftime(TIME_FORMAT)
    )

def get_notification_text(trigger_event, title, organizer_time):
    messages = {
        TriggerEvent.BOOKING_CREATED: f"Создано бронирование {title} на {organizer_time}",
        TriggerEvent.BOOKING_RESCHEDULED: f"Бронирование {title} перенесено на {organizer_time}",
        TriggerEvent.BOOKING_CANCELLED: f"Бронирование {title} на {organizer_time} отменено",
    }
    return messages.get(trigger_event, "")


async def update_description_by_chat_openai(booking_event: BookingEvent):
    chat_completion = await client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": OPENAI_CONTENT_TEMPLATE.format(request=booking_event.payload.description),
            }
        ],
        model="gpt-4o",
    )
    openai_answer = chat_completion.choices[0].message.content
    async with Database(cfg.postgres_dsn) as database:
        query = """UPDATE "Booking" SET description = :description WHERE id = :id"""
        description = f"""
                {openai_answer}

                Оригинальное сообщение:
                {booking_event.payload.description}
                """
        await database.execute(query=query, values={"id": booking_event.payload.booking_id, "description": description})


@root_router.post("/booking")
async def booking(
    booking_event: BookingEvent, request: Request, signature: Annotated[str | None, Header(alias="x-cal-signature-256")]
) -> None:
    if not cfg.debug and not await validate_signature(signature=signature, request=request):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Signature validation error")

    # if booking_event.trigger_event == TriggerEvent.BOOKING_CREATED:
    #     create_task(update_description_by_chat_openai(booking_event=booking_event))

    organizer_chat_id = await get_organizer_chat_id(booking_event.payload.organizer.email)

    if not organizer_chat_id:
        return None

    organizer_time = get_organizer_time(
        organizer_tz=pytz.timezone(booking_event.payload.organizer.time_zone),
        start_time=booking_event.payload.start_time,
    )

    if notification_text := get_notification_text(
        trigger_event=booking_event.trigger_event,
        title=booking_event.payload.title,
        organizer_time=organizer_time,
    ):
        await bot.send_message(
            chat_id=organizer_chat_id,
            text=notification_text,
        )
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
