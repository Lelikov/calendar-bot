import json
from datetime import datetime
from typing import Annotated

import pytz
import structlog
from aiogram import types
from fastapi import APIRouter, Header
from starlette.requests import Request

from bot import bot, dp
from settings import get_settings


logger = structlog.get_logger(__name__)


cfg = get_settings()

root_router = APIRouter(
    prefix="",
    tags=["root"],
    responses={404: {"description": "Not found"}},
)


@root_router.get("/")
async def root() -> dict:
    return {"message": "Hello World"}


@root_router.post("/booking")
async def booking(request: Request) -> None:
    logger.info(f"Request method: {request.method} URL: {request.url}")
    body = json.loads(await request.body())
    tz = pytz.timezone(body["payload"]["organizer"]["timeZone"])
    if body.get("triggerEvent") == "BOOKING_CREATED":
        dt_utc = datetime.strptime(body["payload"]["startTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        dt = dt_utc.astimezone(tz)
        await bot.send_message(
            chat_id=7796298333,
            text=f"Создано бронирование {body["payload"]["title"]} на {dt.strftime("%d-%m-%Y %H:%M")}",
        )
    if body.get("triggerEvent") == "BOOKING_RESCHEDULED":
        dt_utc = datetime.strptime(body["payload"]["startTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        dt = dt_utc.astimezone(tz)
        await bot.send_message(
            chat_id=7796298333,
            text=f"Бронирование {body["payload"]["title"]} перенесено на {dt.strftime("%d-%m-%Y %H:%M")}",
        )
    if body.get("triggerEvent") == "BOOKING_CANCELLED":
        dt_utc = datetime.fromisoformat(body["payload"]["startTime"])
        dt = dt_utc.astimezone(tz)
        await bot.send_message(
            chat_id=7796298333,
            text=f"Бронирование {body["payload"]["title"]} на {dt.strftime("%d-%m-%Y %H:%M")} отменено",
        )


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
