import structlog
from aiogram import Bot
from aiogram.types import BotCommand, WebhookInfo

from app.settings import Settings
from app.system import is_first_run


logger = structlog.get_logger(__name__)


class TelegramService:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def _set_webhook(self, base_webhook_url: str) -> None:
        async def check_webhook() -> WebhookInfo | None:
            try:
                return await self.bot.get_webhook_info()
            except Exception:
                logger.exception("Can't get webhook info")
                return None

        current_webhook_info = await check_webhook()
        if self.settings.debug:
            logger.debug(f"Current bot info: {current_webhook_info}")
        try:
            await self.bot.set_webhook(
                f"{base_webhook_url}{self.settings.webhook_path}",
                secret_token=self.settings.telegram_my_token,
                drop_pending_updates=current_webhook_info.pending_update_count > 0,
                max_connections=40 if self.settings.debug else 100,
            )
            if self.settings.debug:
                logger.debug(f"Updated bot info: {await check_webhook()}")
        except Exception:
            logger.exception("Can't set webhook")

    async def _set_bot_commands_menu(self) -> None:
        commands = [
            BotCommand(command="/id", description="👋 Get my ID"),
        ]
        try:
            await self.bot.set_my_commands(commands)
        except Exception:
            logger.exception("Can't set commands")

    async def start(self) -> None:
        fr = True
        if self.settings.is_check_first_run:
            fr = await is_first_run()
            if self.settings.debug:
                logger.debug(f"First run: {fr}")

        if fr:
            await self._set_webhook(self.settings.base_webhook_url)
            await self._set_bot_commands_menu()
