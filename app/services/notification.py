from datetime import datetime
from typing import ClassVar

import pytz
import structlog
from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from babel.dates import get_timezone_location
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.email import EmailService
from app.dtos import (
    BookingDTO,
    TriggerEvent,
    UserDTO,
)
from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()

TIME_FORMAT = "%d-%m-%Y, %H:%M"


class NotificationService:
    EMAIL_TEMPLATES: ClassVar = {
        "organizer": {
            TriggerEvent.BOOKING_CREATED: ("organizer/confirmation.html", "✅Новая запись"),
            TriggerEvent.BOOKING_RESCHEDULED: ("organizer/reschedule.html", "↻Встреча перенесена"),
            TriggerEvent.BOOKING_CANCELLED: ("organizer/cancellation.html", "❌Встреча отменена"),
        },
        "client": {
            TriggerEvent.BOOKING_CREATED: ("client/confirmation.html", "✅Новая запись"),
            TriggerEvent.BOOKING_RESCHEDULED: ("client/reschedule.html", "↻Встреча перенесена"),
            TriggerEvent.BOOKING_CANCELLED: ("client/cancellation.html", "❌Ваша встреча отменена"),
            TriggerEvent.BOOKING_REMINDER: ("client/reminder.html", "📝Напоминание о встречи с волонтером"),  # noqa: RUF001
        },
    }

    def __init__(self, db: BookingDatabaseAdapter, bot: Bot) -> None:
        self.db = db
        self.bot = bot
        self.jinja_env = Environment(
            loader=FileSystemLoader("app/templates"),
            autoescape=select_autoescape(),
        )
        self.email_service = EmailService(from_email=cfg.from_email, from_email_name=cfg.from_email_name)
        self.timeshift = 5 * 60

    @staticmethod
    def get_time_zone_city(*, time_zone: str) -> str:
        return get_timezone_location(time_zone, locale="ru", return_city=True)

    @staticmethod
    def _get_participant_time(participant_tz_str: str, start_time: datetime | None) -> str:
        if not start_time:
            return ""
        return start_time.astimezone(pytz.timezone(participant_tz_str)).strftime(TIME_FORMAT)

    def _calculate_duration(self, start_time: datetime, end_time: datetime) -> str:
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = int((duration_seconds - self.timeshift) / 60)
        return f"{duration_minutes} мин"

    def _get_notification_text(
        self,
        *,
        time_zone: str,
        start_time: datetime,
        meeting_url: str | None,
        booking_uid: str,
        trigger_event: TriggerEvent,
        previous_start_time: datetime | None = None,
    ) -> str | None:
        organizer_time = self._get_participant_time(
            participant_tz_str=time_zone,
            start_time=start_time,
        )

        messages = {}

        if trigger_event == TriggerEvent.BOOKING_CREATED:
            messages[TriggerEvent.BOOKING_CREATED] = f"""✅ <b>Новая запись</b>

📅 <b>Время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}

🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="{cfg.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>"""

        if trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            previous_time = self._get_participant_time(participant_tz_str=time_zone, start_time=previous_start_time)
            messages[TriggerEvent.BOOKING_RESCHEDULED] = f"""↻ <b>Встреча перенесена</b>

📅 <b>Предыдущее время начала:</b> {previous_time}
📅 <b>Новое время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}

🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="{cfg.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>"""

        if trigger_event == TriggerEvent.BOOKING_CANCELLED:
            messages[TriggerEvent.BOOKING_CANCELLED] = f"""❌ <b>Встреча отменена</b>

📅 <b>Время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}
👤 <a href="{cfg.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>"""

        return messages.get(trigger_event)

    async def notify_organizer_telegram(
        self,
        user: UserDTO,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        organizer_chat_id = await self.db.get_organizer_chat_id(user.email)
        if not organizer_chat_id:
            logger.warning("Organizer chat ID not found", email=user.email)
            return

        notification_text = self._get_notification_text(
            time_zone=user.time_zone,
            meeting_url=meeting_url,
            start_time=booking.start_time,
            booking_uid=booking.uid,
            trigger_event=trigger_event,
            previous_start_time=booking.previous_booking.start_time if booking.previous_booking else None,
        )

        if notification_text:
            logger.info("Sending notification to organizer", email=user.email, trigger_event=trigger_event)
            await self.bot.send_message(
                chat_id=organizer_chat_id,
                text=notification_text,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

    def _prepare_email_context(
        self,
        *,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        participant_time_zone: str,
        meeting_url: str | None,
        additional_context: dict,
    ) -> dict:
        participant_time = self._get_participant_time(participant_time_zone, booking.start_time)

        context = {
            "duration": self._calculate_duration(booking.start_time, booking.end_time),
            "time_zone": self.get_time_zone_city(time_zone=participant_time_zone),
            "meeting_url": meeting_url,
            "cancellation_reason": booking.cancellation_reason,
            **additional_context,
        }

        if trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            previous_time = self._get_participant_time(
                participant_time_zone,
                booking.previous_booking.start_time if booking.previous_booking else None,
            )
            context["start_time"] = previous_time
            context["reschedule_start_time"] = participant_time
        else:
            context["start_time"] = participant_time

        return context

    async def _send_email_notification(
        self,
        *,
        recipient_email: str,
        role: str,
        trigger_event: TriggerEvent,
        context: dict,
    ) -> None:
        template_info = self.EMAIL_TEMPLATES.get(role, {}).get(trigger_event)
        if not template_info:
            logger.warning("No email template for trigger event", trigger_event=trigger_event, role=role)
            return

        template_name, subject = template_info

        try:
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**context)
            await self.email_service.send_email(to_email=recipient_email, subject=subject, html_content=html_content)
            logger.info(f"Sending email to {role}", email=recipient_email, trigger_event=trigger_event)
        except Exception:
            logger.exception(f"Error sending email to {role}")

    async def notify_organizer_email(
        self,
        organizer: UserDTO,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        context = self._prepare_email_context(
            booking=booking,
            trigger_event=trigger_event,
            participant_time_zone=organizer.time_zone,
            meeting_url=meeting_url,
            additional_context={
                "organizer_name": organizer.name,
                "client_name": booking.client.name,
            },
        )

        await self._send_email_notification(
            recipient_email=organizer.email,
            role="organizer",
            trigger_event=trigger_event,
            context=context,
        )

    async def notify_organizer(
        self,
        user: UserDTO,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        await self.notify_organizer_telegram(user, booking, trigger_event, meeting_url)
        await self.notify_organizer_email(user, booking, trigger_event, meeting_url)

    async def notify_client_email(
        self,
        *,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        context = self._prepare_email_context(
            booking=booking,
            participant_time_zone=booking.client.time_zone,
            trigger_event=trigger_event,
            meeting_url=meeting_url,
            additional_context={
                "client_name": booking.client.name,
                "cancel_link": f"{cfg.booking_host_url}/booking/{booking.uid}",
                "support_email": cfg.support_email,
            },
        )

        await self._send_email_notification(
            recipient_email=booking.client.email,
            role="client",
            trigger_event=trigger_event,
            context=context,
        )

    async def notify_client(
        self,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        await self.notify_client_email(
            booking=booking,
            trigger_event=trigger_event,
            meeting_url=meeting_url,
        )
