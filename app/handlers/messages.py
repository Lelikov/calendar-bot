import binascii

import structlog
from aiogram import F, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.utils.payload import decode_payload
from databases import Database

from app.bot import telegram_router
from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()


@telegram_router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Your ID: {message.from_user.id} Your chat ID: {message.chat.id}")


@telegram_router.message(CommandStart(deep_link=True))
async def cmd_start(message: Message, command: CommandObject) -> None:
    try:
        user_id, telegram_token = decode_payload(command.args).split("@")
        user_id = int(user_id)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        logger.exception(f"Wrong payload {command.args}")
        await message.answer("Ошибка регистрации. Обратитесь к администратору")
        return None

    async with Database(cfg.postgres_dsn) as database:
        query = "SELECT name, telegram_chat_id, telegram_token FROM users WHERE locked = FALSE AND id = :id "
        row = await database.fetch_one(query=query, values={"id": user_id})

    if not row:
        return None

    if row["telegram_chat_id"]:
        await message.answer("Ваш email уже зарегистрирован")
        return None

    if row["telegram_token"] == telegram_token:
        async with Database(cfg.postgres_dsn) as database:
            query = "UPDATE users SET telegram_chat_id = :telegram_chat_id WHERE id = :id"
            await database.execute(query=query, values={"id": user_id, "telegram_chat_id": message.chat.id})
            await message.answer(f"Добро пожаловать, {hbold(row['name'])}")
    return None


@telegram_router.message(F.text == "ping")
async def hello(message: types.Message) -> None:
    try:
        await message.answer("pong")
    except Exception:
        logger.exception("Can't send message")
        await message.answer("Nice try!")
