from datetime import datetime
from typing import ClassVar

import pytz
import structlog
from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from babel.dates import get_timezone_location

from app.dtos import (
    BookingDTO,
    TriggerEvent,
    UserDTO,
)
from app.interfaces import INotificationController
from app.interfaces.booking import IBookingDatabaseAdapter
from app.interfaces.mail import IEmailController
from app.settings import Settings


logger = structlog.get_logger(__name__)

TIME_FORMAT = "%d-%m-%Y, %H:%M"


class NotificationController(INotificationController):
    EMAIL_TEMPLATES: ClassVar = {
        "organizer": {
            TriggerEvent.BOOKING_CREATED: "e05d2280-3286-11f1-b49a-aa5f97242f68",
            TriggerEvent.BOOKING_RESCHEDULED: "88afe254-327f-11f1-bc88-66028c6421c3",
            TriggerEvent.BOOKING_CANCELLED: "e825b1ee-3281-11f1-8ffc-aa5f97242f68",
        },
        "client": {
            TriggerEvent.BOOKING_CREATED: "be078446-2d1d-11f1-a53a-66028c6421c3",
            TriggerEvent.BOOKING_RESCHEDULED: "33d00cce-3283-11f1-ba1f-66028c6421c3",
            TriggerEvent.BOOKING_CANCELLED: "458af1da-2e60-11f1-ab1f-aa5f97242f68",
            TriggerEvent.BOOKING_REMINDER: "84fe871e-2dd4-11f1-a2fc-66028c6421c3",
            TriggerEvent.BOOKING_REJECTED: "7bd3f34a-3284-11f1-948b-aa5f97242f68",
        },
    }

    def __init__(
        self,
        db: IBookingDatabaseAdapter,
        bot: Bot,
        settings: Settings,
        email_controller: IEmailController,
    ) -> None:
        self.db = db
        self.bot = bot
        self.settings = settings
        self.email_controller = email_controller
        self.timeshift = 10 * 60

    @staticmethod
    def get_time_zone_city(*, time_zone: str) -> str:
        return get_timezone_location(time_zone, locale="ru", return_city=True)

    @staticmethod
    def _get_participant_time(participant_tz_str: str, start_time: datetime | None) -> str:
        if not start_time:
            return ""
        return start_time.astimezone(pytz.timezone(participant_tz_str)).strftime(TIME_FORMAT)

    @staticmethod
    def _build_previous_meetings_html(meeting_dates: list[str]) -> str:
        if not meeting_dates:
            return ""
        items = "".join(f'<li style="margin-bottom: 4px;">{date}</li>' for date in meeting_dates)
        return (
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation"'
            ' style="background-color: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb; margin-bottom: 24px;">'
            '<tr><td style="padding: 24px;">'
            '<p style="margin: 0 0 12px 0; color: #374151; font-size: 16px; font-family: inherit;">'
            "<strong>Ваши последние встречи:</strong></p>"
            '<ul style="margin: 0; padding-left: 20px; color: #4b5563; font-size: 15px; line-height: 1.6; '
            'font-family: inherit;">'
            f"{items}"
            "</ul></td></tr></table>"
        )

    @staticmethod
    def _build_rejection_reason(
        *,
        rejection_type: str | None,
        active_booking_start_text: str | None,
        last_meeting_date: str | None,
    ) -> str:
        if rejection_type == "has_active_booking":
            return (
                f"У вас уже есть одна подтверждённая встреча с психологом-волонтером на {active_booking_start_text}, "
                "поэтому мы не можем записать вас на консультацию. "
                "По правилам проекта, нельзя записаться на несколько консультаций одновременно."
            )
        if rejection_type == "month_limit":
            return (
                "В этом месяце вы уже использовали доступный лимит — 2 встречи, поэтому мы не можем записать вас "
                "на консультацию с психологом-волонтёром."
            )
        if rejection_type == "year_limit":
            return (
                "В этом году вы уже использовали доступный лимит — 10 встреч, поэтому мы не можем записать вас "
                "на консультацию с психологом-волонтёром."
            )
        if rejection_type == "min_interval":
            date_part = f" ({last_meeting_date})" if last_meeting_date else ""
            return (
                f"С момента вашей последней встречи{date_part} прошло менее 7 календарных дней, поэтому мы не "
                f"можем записать вас на консультацию с психологом-волонтёром."
            )
        if rejection_type == "cancelled_booking":
            date_part = f" ({last_meeting_date})" if last_meeting_date else ""
            return (
                f"Ваша последняя запись{date_part} была отменена. По правилам проекта, следующая консультация "
                "возможна не ранее чем через 2 месяца после отмены, поэтому мы не можем записать вас "
                "на консультацию с психологом-волонтёром."
            )
        return "К сожалению, сейчас мы не можем подтвердить вашу запись."

    def _calculate_duration(self, start_time: datetime, end_time: datetime) -> str:
        duration_seconds = (end_time - start_time).total_seconds()
        duration_minutes = int((duration_seconds - self.timeshift) / 60)
        return f"{duration_minutes} минут"

    def _get_telegram_notification_text(
        self,
        *,
        booking: BookingDTO,
        time_zone: str,
        meeting_url: str | None,
        trigger_event: TriggerEvent,
    ) -> str | None:
        start_time = booking.start_time
        booking_uid = booking.uid
        previous_start_time = booking.previous_booking.start_time if booking.previous_booking else None
        organizer_time = self._get_participant_time(participant_tz_str=time_zone, start_time=start_time)

        messages = {}

        if trigger_event == TriggerEvent.BOOKING_CREATED:
            messages[TriggerEvent.BOOKING_CREATED] = f"""✅ <b>Новая запись</b>

📅 <b>Время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}

🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="{self.settings.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>"""

        if trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            previous_time = self._get_participant_time(participant_tz_str=time_zone, start_time=previous_start_time)
            messages[TriggerEvent.BOOKING_RESCHEDULED] = f"""↻ <b>Встреча перенесена</b>

📅 <b>Предыдущее время начала:</b> {previous_time}
📅 <b>Новое время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}

🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="{self.settings.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>"""

        if trigger_event == TriggerEvent.BOOKING_CANCELLED:
            messages[TriggerEvent.BOOKING_CANCELLED] = f"""❌ <b>Встреча отменена</b>

📅 <b>Время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}
👤 <a href="{self.settings.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>"""

        if trigger_event == TriggerEvent.MEET_CLIENT_JOINED:
            messages[TriggerEvent.MEET_CLIENT_JOINED] = f"""🏃<b>Клиент зашел на встречу</b>

📅 <b>Время начала:</b> {organizer_time}
🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="{self.settings.booking_host_url}/booking/{booking_uid}">Информация o клиенте</a>

⚠️ Если после этого сообщения вы не видите клиента, обновите страницу встречи в браузере и подключитесь снова ⚠️
"""

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

        notification_text = self._get_telegram_notification_text(
            booking=booking,
            time_zone=user.time_zone,
            meeting_url=meeting_url,
            trigger_event=trigger_event,
        )

        if notification_text:
            logger.info("Sending telegram notification to organizer", email=user.email, trigger_event=trigger_event)
            try:
                await self.bot.send_message(
                    chat_id=organizer_chat_id,
                    text=notification_text,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception:
                logger.exception("Error sending telegram notification", email=user.email, trigger_event=trigger_event)

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
            "Duration": self._calculate_duration(booking.start_time, booking.end_time),
            "TimeZone": self.get_time_zone_city(time_zone=participant_time_zone),
            "MeetingUrl": meeting_url.replace("https://", "") if meeting_url else "",
            **additional_context,
        }

        if trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            previous_time = self._get_participant_time(
                participant_time_zone,
                booking.previous_booking.start_time if booking.previous_booking else None,
            )
            context["StartTime"] = previous_time
            context["RescheduleStartTime"] = participant_time
        else:
            context["StartTime"] = participant_time

        return context

    async def _send_email_notification(
        self,
        *,
        recipient_email: str,
        role: str,
        trigger_event: TriggerEvent,
        context: dict,
    ) -> None:
        template_id = self.EMAIL_TEMPLATES.get(role, {}).get(trigger_event)
        if not template_id:
            logger.warning("No email template for trigger event", trigger_event=trigger_event, role=role)
            return

        try:
            logger.info(f"Sending email to {role}", email=recipient_email, trigger_event=trigger_event)
            await self.email_controller.send_email(to_email=recipient_email, context=context, template_id=template_id)
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
                "OrganizerName": organizer.name,
                "ClientName": booking.client.name,
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
                "ClientName": booking.client.name,
                "CancelLink": f"{self.settings.booking_host_url.replace('https://', '')}/booking/{booking.uid}",
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

    async def notify_client_booking_rejected(
        self,
        *,
        booking: BookingDTO,
        available_from: datetime,
        previous_meeting_dates: list[datetime],
        rejection_type: str | None,
        active_booking_start: datetime | None,
    ) -> None:
        try:
            available_from_text = self._get_participant_time(booking.client.time_zone, available_from)
            previous_meeting_dates_text = [
                start_time.astimezone(pytz.timezone(booking.client.time_zone)).strftime("%d.%m.%Y")
                for start_time in previous_meeting_dates
            ]
            rejection_reason = self._build_rejection_reason(
                rejection_type=rejection_type,
                active_booking_start_text=(
                    self._get_participant_time(booking.client.time_zone, active_booking_start)
                    if active_booking_start
                    else None
                ),
                last_meeting_date=previous_meeting_dates_text[0] if previous_meeting_dates_text else None,
            )
            previous_meetings_html = self._build_previous_meetings_html(previous_meeting_dates_text)
            context = {
                "ClientName": booking.client.name,
                "RejectionReason": rejection_reason,
                "AvailableFrom": available_from_text,
                "PreviousMeetings": previous_meetings_html,
            }
            template_id = self.EMAIL_TEMPLATES.get("client", {}).get(TriggerEvent.BOOKING_REJECTED)
            await self.email_controller.send_email(
                to_email=booking.client.email,
                context=context,
                template_id=template_id,
            )
        except Exception:
            logger.exception(
                "Error sending rejected booking notification to client",
                booking_uid=booking.uid,
                client_email=booking.client.email,
            )
