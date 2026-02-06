import binascii
import time
import uuid

import jwt
import structlog
from aiogram import F, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.utils.payload import decode_payload

from app.adapters.get_stream import GetStreamAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.bot import telegram_router
from app.controllers.chat import ChatController
from app.database import database
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

    query = "SELECT name, telegram_chat_id, telegram_token FROM users WHERE locked = FALSE AND id = :id "
    row = await database.fetch_one(query=query, values={"id": user_id})

    if not row:
        return None

    if row["telegram_chat_id"]:
        await message.answer("Ваш email уже зарегистрирован")
        return None

    if row["telegram_token"] == telegram_token:
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


@telegram_router.message(Command("meeting_test"))
async def meeting_test(message: types.Message, command: CommandObject) -> None:
    args = (command.args or "").split(",")
    if not args or len(args) != 2:
        await message.answer("Введите имя и почту второго участника через запятую")
        return None
    client_email = next((x for x in args if "@" in x), "").strip()
    client_name = next((x for x in args if x is not client_email), "").strip()
    if not client_email:
        await message.answer(f"Почта второго участника {client_email} указана неправильно")
        return None

    query = "SELECT name, email FROM users WHERE locked = FALSE AND telegram_chat_id = :telegram_chat_id "
    row = await database.fetch_one(query=query, values={"telegram_chat_id": message.from_user.id})

    if not row:
        return None

    organizer_name = row["name"]
    organizer_email = row["email"]

    meeting_uid = str(uuid.uuid4())
    start_time = int(time.time())
    end_time = start_time + 60 * 60

    def create_jitsi_token(participant_name: str, role: str) -> str:
        payload = {
            "aud": cfg.meeting_jwt_aud,
            "iss": cfg.meeting_jwt_iss,
            "sub": "*",
            "room": meeting_uid,
            "iat": start_time,
            "nbf": start_time,
            "exp": end_time,
            "context": {"user": {"name": participant_name, "role": role}},
        }
        return jwt.encode(payload, cfg.jitsi_jwt_token, algorithm="HS256")

    client_video_token = create_jitsi_token(client_name, role="client")
    organizer_video_token = create_jitsi_token(organizer_name, role="organizer")

    chat_adapter = GetStreamAdapter(
        chat_api_key=cfg.chat_api_key,
        chat_api_secret=cfg.chat_api_secret,
        user_id_encryption_key=cfg.chat_user_id_encryption_key,
    )
    chat_controller = ChatController(client=chat_adapter)

    await chat_controller.create_chat(
        channel_id=meeting_uid,
        organizer_id=organizer_email,
        client_id=client_email,
    )

    client_chat_token = chat_controller.create_token(
        user_id=client_email,
        name=client_name,
        expires_at=end_time,
    )
    organizer_chat_token = chat_controller.create_token(
        user_id=organizer_email,
        name=organizer_name,
        expires_at=end_time,
    )

    client_long_url = (
        f"{cfg.meeting_host_url}/{meeting_uid}?jwt_video={client_video_token}&jwt_chat={client_chat_token}"
    )
    organizer_long_url = (
        f"{cfg.meeting_host_url}/{meeting_uid}?jwt_video={organizer_video_token}&jwt_chat={organizer_chat_token}"
    )
    shortner = UrlShortenerAdapter()
    client_short_url = await shortner.create_url(
        external_id=f"client_{meeting_uid}",
        long_url=client_long_url,
        expires_at=end_time,
    )
    organizer_short_url = await shortner.create_url(
        external_id=f"{meeting_uid}",
        long_url=organizer_long_url,
        expires_at=end_time,
    )

    await message.answer(f"Ваша ссылка для подключения {organizer_short_url}\nСсылка для клиента {client_short_url}")
    return None
