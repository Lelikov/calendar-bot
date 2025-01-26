import structlog
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, WebhookInfo

from app.settings import Settings, get_settings
from app.system import is_first_run


logger = structlog.get_logger(__name__)

cfg: Settings = get_settings()

dp = Dispatcher()
telegram_router = Router(name="telegram")
dp.include_router(telegram_router)

bot = Bot(token=cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


async def set_webhook(my_bot: Bot, base_webhook_url: str) -> None:
    async def check_webhook() -> WebhookInfo | None:
        try:
            return await my_bot.get_webhook_info()
        except Exception:
            logger.exception("Can't get webhook info")
            return None

    current_webhook_info = await check_webhook()
    if cfg.debug:
        logger.debug(f"Current bot info: {current_webhook_info}")
    try:
        await my_bot.set_webhook(
            f"{base_webhook_url}{cfg.webhook_path}",
            secret_token=cfg.telegram_my_token,
            drop_pending_updates=current_webhook_info.pending_update_count > 0,
            max_connections=40 if cfg.debug else 100,
        )
        if cfg.debug:
            logger.debug(f"Updated bot info: {await check_webhook()}")
    except Exception:
        logger.exception("Can't set webhook")


async def set_bot_commands_menu(my_bot: Bot) -> None:
    commands = [
        BotCommand(command="/id", description="👋 Get my ID"),
    ]
    try:
        await my_bot.set_my_commands(commands)
    except Exception:
        logger.exception("Can't set commands")


async def start_telegram(base_webhook_url: str) -> None:
    fr = True
    if cfg.is_check_first_run:
        fr = await is_first_run()
        if cfg.debug:
            logger.debug(f"First run: {fr}")

    if fr:
        await set_webhook(bot, base_webhook_url)
        await set_bot_commands_menu(bot)

