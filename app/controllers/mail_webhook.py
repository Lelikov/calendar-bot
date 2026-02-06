import structlog
from aiogram import Bot
from aiogram.types import LinkPreviewOptions

from app.dtos import MailWebhookEventDTO
from app.settings import Settings


logger = structlog.get_logger(__name__)

processed_mail_webhook_ids: set[int] = set()


class MailWebhookController:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def handle_webhook(self, event: MailWebhookEventDTO) -> None:
        if event.payload.message.id in processed_mail_webhook_ids:
            return None
        processed_mail_webhook_ids.add(event.payload.message.id)

        text = (
            f"Mail webhook event:\n\n"
            f"<b>To:</b> {event.payload.message.to}\n"
            f"<b>Status:</b> {event.payload.status}\n"
            f"<b>Output:</b> {event.payload.output}"
        )

        for chat_id in self.settings.admin_chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception:
                logger.exception("Failed to send mail webhook notification", chat_id=chat_id)
        return None
