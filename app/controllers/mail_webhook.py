import structlog
from aiogram import Bot
from aiogram.types import LinkPreviewOptions

from app.dtos import MailWebhookEventDTO
from app.settings import Settings


logger = structlog.get_logger(__name__)

processed_mail_webhook_ids: set[str] = set()


class MailWebhookController:
    def __init__(self, bot: Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    async def handle_webhook(self, event: MailWebhookEventDTO) -> None:
        for user_events in event.events_by_user:
            for user_event in user_events.events:
                deduplicate_key = (
                    f"{user_events.user_id}:{user_event.event_data.job_id}:"
                    f"{user_event.event_data.status}:{user_event.event_data.event_time}"
                )
                if deduplicate_key in processed_mail_webhook_ids:
                    continue
                processed_mail_webhook_ids.add(deduplicate_key)

                text = (
                    f"Mail webhook event:\n\n"
                    f"<b>Email:</b> {user_event.event_data.email}\n"
                    f"<b>Status:</b> {user_event.event_data.status}\n"
                    f"<b>Delivery status:</b> {user_event.event_data.delivery_info.delivery_status}\n"
                    f"<b>Response:</b> {user_event.event_data.delivery_info.destination_response}"
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
