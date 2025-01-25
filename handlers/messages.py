import structlog
from aiogram import F, types
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from databases import Database

from bot import telegram_router
from settings import get_settings

logger = structlog.get_logger(__name__)
cfg = get_settings()


@telegram_router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Your ID: {message.from_user.id} Your chat ID: {message.chat.id}")


@telegram_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    payload = (message.text or "").split("/start ")
    email = payload[1] if len(payload) > 1 else None

    async with Database(cfg.postgres_dsn) as database:
        query = "SELECT * FROM users WHERE email = :email"
        row = await database.fetch_one(query=query, values={"email": email})
    await message.answer(f"Hello, {hbold(row["name"])}!")


@telegram_router.message(F.text == "echo")
async def echo(message: types.Message) -> None:
    try:
        await message.send_copy(chat_id=message.chat.id)
    except Exception:
        logger.exception("Can't send message")
        await message.answer("Nice try!")


@telegram_router.message(F.text == "ping")
async def hello(message: types.Message) -> None:
    try:
        await message.answer("pong")
    except Exception:
        logger.exception("Can't send message")
        await message.answer("Nice try!")