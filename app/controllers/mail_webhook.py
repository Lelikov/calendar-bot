from datetime import UTC, datetime

import structlog
from aiogram import Bot
from aiogram.types import LinkPreviewOptions

from app.dtos import EmailEventDTO, MailWebhookEventDTO, MailWebhookUserEventDTO
from app.interfaces.mail import IEmailEventDatabaseAdapter
from app.settings import Settings


logger = structlog.get_logger(__name__)

EMAIL_STATUS_EVENT = "transactional_email_status"
EVENT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class MailWebhookController:
    def __init__(self, bot: Bot, settings: Settings, email_event_db: IEmailEventDatabaseAdapter) -> None:
        self.bot = bot
        self.settings = settings
        self.email_event_db = email_event_db

    async def handle_webhook(self, event: MailWebhookEventDTO) -> None:
        for user_events in event.events_by_user:
            for user_event in user_events.events:
                email_event = self._to_email_event(user_event)
                if not email_event:
                    continue

                # The insert is what deduplicates: a repeated webhook call finds the
                # event already stored and must not be reported a second time.
                if not await self.email_event_db.save_event(email_event):
                    continue

                await self._notify_admins(email_event)
        return None

    @staticmethod
    def _to_email_event(user_event: MailWebhookUserEventDTO) -> EmailEventDTO | None:
        """Turn a webhook event into a storable one, or None if it is not ours.

        The same Unisender project sends emails for other systems, and those events
        arrive through this very webhook without a booking_uid. We answer 200 to all of
        them - only the ones we can tie to a meeting are kept.
        """
        if user_event.event_name != EMAIL_STATUS_EVENT:
            return None

        data = user_event.event_data
        booking_uid = (data.metadata or {}).get("booking_uid")
        if not booking_uid:
            return None

        if not (data.job_id and data.email and data.status and data.event_time):
            logger.warning(
                "Skipping email status event without required fields",
                booking_uid=booking_uid,
                job_id=data.job_id,
                status=data.status,
            )
            return None

        event_time = MailWebhookController._parse_event_time(data.event_time)
        if not event_time:
            logger.warning(
                "Skipping email status event with unparsable event_time",
                booking_uid=booking_uid,
                event_time=data.event_time,
            )
            return None

        return EmailEventDTO(
            booking_uid=booking_uid,
            job_id=data.job_id,
            email=data.email,
            status=data.status,
            event_time=event_time,
            trigger_event=data.metadata.get("trigger_event") if data.metadata else None,
            role=data.metadata.get("role") if data.metadata else None,
            delivery_status=data.delivery_info.delivery_status if data.delivery_info else None,
            destination_response=data.delivery_info.destination_response if data.delivery_info else None,
        )

    @staticmethod
    def _parse_event_time(event_time: str) -> datetime | None:
        """Unisender sends "YYYY-MM-DD hh:mm:ss" in UTC."""
        try:
            return datetime.strptime(event_time, EVENT_TIME_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            return None

    async def _notify_admins(self, email_event: EmailEventDTO) -> None:
        text = (
            f"Mail webhook event:\n\n"
            f"<b>Email:</b> {email_event.email}\n"
            f"<b>Booking:</b> {email_event.booking_uid}\n"
            f"<b>Status:</b> {email_event.status}\n"
            f"<b>Delivery status:</b> {email_event.delivery_status}\n"
            f"<b>Response:</b> {email_event.destination_response}"
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
