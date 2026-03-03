import binascii
import time
import uuid
from datetime import UTC, datetime

import jwt
import structlog
from aiogram import F, types
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.utils.payload import decode_payload
from dishka.integrations.aiogram import FromDishka, inject

from app.interfaces.chat import IChatController
from app.interfaces.sql import ISqlExecutor
from app.interfaces.url_shortener import IUrlShortener
from app.ioc import telegram_router
from app.settings import Settings


logger = structlog.get_logger(__name__)


MEETING_TEST_FIELDS: list[tuple[str, str]] = [
    ("client_email", "Введите client_email"),
    ("client_name", "Введите client_name"),
    ("organizer_name", "Введите organizer_name"),
    ("organizer_email", "Введите organizer_email"),
    ("meeting_uid", "Введите meeting_uid"),
    ("start_time", "Введите start_time в формате YYYY-MM-DD HH:MM (UTC)"),
    ("duration_minutes", "Введите продолжительность встречи в минутах"),
]
MEETING_TEST_STATE: dict[int, dict] = {}


async def _send_meeting_test_links(
    *,
    message: types.Message,
    chat_controller: IChatController,
    shortener: IUrlShortener,
    settings: Settings,
    client_email: str,
    client_name: str,
    organizer_name: str,
    organizer_email: str,
    meeting_uid: str,
    start_time: int,
    duration_minutes: int,
) -> None:
    end_time = start_time + 60 * duration_minutes

    def create_jitsi_token(participant_name: str, role: str) -> str:
        payload = {
            "aud": settings.meeting_jwt_aud,
            "iss": settings.meeting_jwt_iss,
            "sub": "*",
            "room": meeting_uid,
            "iat": start_time,
            "nbf": start_time,
            "exp": end_time,
            "context": {"user": {"name": participant_name, "role": role}},
        }
        return jwt.encode(payload, settings.jitsi_jwt_token, algorithm="HS256")

    client_video_token = create_jitsi_token(client_name, role="client")
    organizer_video_token = create_jitsi_token(organizer_name, role="organizer")

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
        f"{settings.meeting_host_url}/{meeting_uid}?jwt_video={client_video_token}&jwt_chat={client_chat_token}"
    )
    organizer_long_url = (
        f"{settings.meeting_host_url}/{meeting_uid}?jwt_video={organizer_video_token}&jwt_chat={organizer_chat_token}"
    )
    client_short_url = await shortener.create_url(
        external_id=f"client_{meeting_uid}",
        long_url=client_long_url,
        expires_at=end_time,
        not_before=start_time,
    )
    organizer_short_url = await shortener.create_url(
        external_id=f"{meeting_uid}",
        long_url=organizer_long_url,
        expires_at=end_time,
        not_before=start_time,
    )

    await message.answer(f"Ваша ссылка для подключения {organizer_short_url}\nСсылка для клиента {client_short_url}")


@telegram_router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Your ID: {message.from_user.id} Your chat ID: {message.chat.id}")


@telegram_router.message(CommandStart(deep_link=True))
@inject
async def cmd_start(
    message: Message,
    command: CommandObject,
    sql: FromDishka[ISqlExecutor],
) -> None:
    try:
        user_id, telegram_token = decode_payload(command.args).split("@")
        user_id = int(user_id)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        logger.exception(f"Wrong payload {command.args}")
        await message.answer("Ошибка регистрации. Обратитесь к администратору")
        return None

    query = "SELECT name, telegram_chat_id, telegram_token FROM users WHERE locked = FALSE AND id = :id "
    row = await sql.fetch_one(query, {"id": user_id})

    if not row:
        return None

    if row["telegram_chat_id"]:
        await message.answer("Ваш email уже зарегистрирован")
        return None

    if row["telegram_token"] == telegram_token:
        query = "UPDATE users SET telegram_chat_id = :telegram_chat_id WHERE id = :id"
        await sql.execute(query, {"id": user_id, "telegram_chat_id": message.chat.id})
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
@inject
async def meeting_test(
    message: types.Message,
    command: CommandObject,
    sql: FromDishka[ISqlExecutor],
    chat_controller: FromDishka[IChatController],
    shortener: FromDishka[IUrlShortener],
    settings: FromDishka[Settings],
) -> None:
    args_raw = (command.args or "").strip()

    query = "SELECT name, email FROM users WHERE locked = FALSE AND telegram_chat_id = :telegram_chat_id "
    row = await sql.fetch_one(query, {"telegram_chat_id": message.from_user.id})
    if not row:
        return None

    if not args_raw:
        user_id = message.from_user.id
        MEETING_TEST_STATE[user_id] = {"step": 0, "data": {}}
        await message.answer(
            "Запустил пошаговый режим meeting_test. "
            "Для отмены отправьте /cancel_meeting_test.\n"
            f"{MEETING_TEST_FIELDS[0][1]}",
        )
        return None

    args = [arg.strip() for arg in args_raw.split(",") if arg.strip()]
    if len(args) != 2:
        await message.answer("Введите имя и почту второго участника через запятую")
        return None

    client_email = next((x for x in args if "@" in x), "")
    client_name = next((x for x in args if x != client_email), "")
    if not client_email:
        await message.answer(f"Почта второго участника {client_email} указана неправильно")
        return None

    await _send_meeting_test_links(
        message=message,
        chat_controller=chat_controller,
        shortener=shortener,
        settings=settings,
        client_email=client_email,
        client_name=client_name,
        organizer_name=row["name"],
        organizer_email=row["email"],
        meeting_uid=str(uuid.uuid4()),
        start_time=int(time.time()),
        duration_minutes=60,
    )
    return None


@telegram_router.message(Command("cancel_meeting_test"))
async def cancel_meeting_test(message: types.Message) -> None:
    user_id = message.from_user.id
    MEETING_TEST_STATE.pop(user_id, None)
    await message.answer("Пошаговый режим meeting_test отменен")


@telegram_router.message()
@inject
async def meeting_test_interactive(
    message: types.Message,
    chat_controller: FromDishka[IChatController],
    shortener: FromDishka[IUrlShortener],
    settings: FromDishka[Settings],
) -> None:
    user_id = message.from_user.id
    state = MEETING_TEST_STATE.get(user_id)
    if not state:
        return None

    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите значение текстом")
        return None

    step: int = state["step"]
    field_name = MEETING_TEST_FIELDS[step][0]

    if field_name in {"client_email", "organizer_email"} and "@" not in text:
        await message.answer(f"{field_name} указан неправильно, попробуйте снова")
        return None

    if field_name == "duration_minutes":
        if not text.isdigit():
            await message.answer("duration_minutes должен быть целым числом")
            return None
        value = int(text)
        if value <= 0:
            await message.answer("duration_minutes должен быть больше 0")
            return None
        state["data"][field_name] = value
    elif field_name == "start_time":
        try:
            parsed_dt = datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
        except ValueError:
            await message.answer("start_time должен быть в формате YYYY-MM-DD HH:MM (UTC)")
            return None
        state["data"][field_name] = int(parsed_dt.timestamp())
    else:
        state["data"][field_name] = text

    next_step = step + 1
    if next_step < len(MEETING_TEST_FIELDS):
        state["step"] = next_step
        await message.answer(MEETING_TEST_FIELDS[next_step][1])
        return None

    data = state["data"]
    MEETING_TEST_STATE.pop(user_id, None)

    await _send_meeting_test_links(
        message=message,
        chat_controller=chat_controller,
        shortener=shortener,
        settings=settings,
        client_email=data["client_email"],
        client_name=data["client_name"],
        organizer_name=data["organizer_name"],
        organizer_email=data["organizer_email"],
        meeting_uid=data["meeting_uid"],
        start_time=data["start_time"],
        duration_minutes=data["duration_minutes"],
    )
    return None
