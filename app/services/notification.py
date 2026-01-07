import pytz
import structlog
from aiogram import Bot
from aiogram.types import LinkPreviewOptions
from babel.dates import get_timezone_location
from dateutil import parser
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.email import EmailService
from app.schemas import BookingEventAttendee, BookingEventOrganizer, BookingEventPayload, TriggerEvent
from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()

TIME_FORMAT = "%d-%m-%Y %H:%M"


class NotificationService:
    def __init__(self, db: BookingDatabaseAdapter, bot: Bot) -> None:
        self.db = db
        self.bot = bot
        self.jinja_env = Environment(
            loader=FileSystemLoader("app/templates"),
            autoescape=select_autoescape(),
        )
        self.email_service = EmailService(
            host=cfg.smtp_host,
            port=cfg.smtp_port,
            from_email=cfg.smtp_from,
        )

    @staticmethod
    def get_time_zone_city(*, time_zone: str) -> str:
        return get_timezone_location(time_zone, locale="ru", return_city=True)

    @staticmethod
    def _get_organizer_time(organizer_tz_str: str, start_time: str | None) -> str:
        if not start_time:
            return ""
        organizer_tz = pytz.timezone(organizer_tz_str)
        parsed_time = parser.parse(start_time)
        return parsed_time.astimezone(organizer_tz).strftime(TIME_FORMAT)

    def _get_notification_text(
        self,
        *,
        time_zone: str,
        start_time: str,
        meeting_url: str | None,
        booking_uid: str,
        trigger_event: TriggerEvent,
        reschedule_start_time: str | None = None,
    ) -> str | None:
        organizer_time = self._get_organizer_time(
            organizer_tz_str=time_zone,
            start_time=start_time,
        )

        messages = {}

        if trigger_event == TriggerEvent.BOOKING_CREATED:
            messages[TriggerEvent.BOOKING_CREATED] = f"""✅ <b>Новая запись</b>

📅 <b>Время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}

🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="https://booking.zhivaya.org/booking/{booking_uid}">Информация o клиенте</a>"""

        elif trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            previous_time = self._get_organizer_time(organizer_tz_str=time_zone, start_time=reschedule_start_time)
            messages[TriggerEvent.BOOKING_RESCHEDULED] = f"""↻ <b>Встреча перенесена</b>

📅 <b>Предыдущее время начала:</b> {previous_time}
📅 <b>Новое время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}

🔗 <a href="{meeting_url}">Ссылка на встречу</a>
👤 <a href="https://booking.zhivaya.org/booking/{booking_uid}">Информация o клиенте</a>"""

        elif trigger_event == TriggerEvent.BOOKING_CANCELLED:
            messages[TriggerEvent.BOOKING_CANCELLED] = f"""❌ <b>Встреча отменена</b>

📅 <b>Время начала:</b> {organizer_time}
🌍 <b>Часовой пояс:</b> {self.get_time_zone_city(time_zone=time_zone)}
👤 <a href="https://booking.zhivaya.org/booking/{booking_uid}">Информация o клиенте</a>"""

        return messages.get(trigger_event)

    async def notify_organizer_telegram(
        self,
        organizer: BookingEventOrganizer,
        booking_event_payload: BookingEventPayload,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        organizer_chat_id = await self.db.get_organizer_chat_id(organizer.email)
        if not organizer_chat_id:
            logger.warning("Organizer chat ID not found", email=organizer.email)
            return

        notification_text = self._get_notification_text(
            time_zone=organizer.time_zone,
            meeting_url=meeting_url,
            start_time=booking_event_payload.start_time,
            booking_uid=booking_event_payload.uid,
            trigger_event=trigger_event,
            reschedule_start_time=booking_event_payload.reschedule_start_time,
        )

        if notification_text:
            logger.info("Sending notification to organizer", email=organizer.email, trigger_event=trigger_event)
            await self.bot.send_message(
                chat_id=organizer_chat_id,
                text=notification_text,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )

    async def notify_organizer_email(
        self,
        organizer: BookingEventOrganizer,
        booking_event_payload: BookingEventPayload,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        template_name = None
        subject = None

        if trigger_event == TriggerEvent.BOOKING_CREATED:
            template_name = "organizer/confirmation.html"
            subject = "✅Новая запись"
        if trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            template_name = "organizer/reschedule.html"
            subject = "↻Встреча перенесена"
        if trigger_event == TriggerEvent.BOOKING_CANCELLED:
            template_name = "organizer/cancellation.html"
            subject = "❌Встреча отменена"

        if not template_name:
            logger.warning("No email template for trigger event", trigger_event=trigger_event)
            return

        attendee_name = booking_event_payload.attendees[0].name if booking_event_payload.attendees else "Unknown"

        start_dt = parser.parse(booking_event_payload.start_time)
        end_dt = parser.parse(booking_event_payload.end_time)
        duration_min = int((end_dt - start_dt).total_seconds() / 60)
        duration = f"{duration_min} мин"

        organizer_time = self._get_organizer_time(organizer.time_zone, booking_event_payload.start_time)

        context = {
            "organizer_name": organizer.name,
            "attendee_name": attendee_name,
            "duration": duration,
            "time_zone": self.get_time_zone_city(time_zone=organizer.time_zone),
            "meeting_url": meeting_url,
            "cancellation_reason": booking_event_payload.cancellation_reason,
        }

        if trigger_event == TriggerEvent.BOOKING_RESCHEDULED:
            previous_time = self._get_organizer_time(organizer.time_zone, booking_event_payload.reschedule_start_time)
            context["start_time"] = previous_time
            context["reschedule_start_time"] = organizer_time
        else:
            context["start_time"] = organizer_time

        try:
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**context)
            self.email_service.send_email(to_email=organizer.email, subject=subject, html_content=html_content)
            logger.info("Sending email to organizer", email=organizer.email, trigger_event=trigger_event)
        except Exception:
            logger.exception("Error sending email to organizer")

    async def notify_organizer(
        self,
        organizer: BookingEventOrganizer,
        booking_event_payload: BookingEventPayload,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        await self.notify_organizer_telegram(organizer, booking_event_payload, trigger_event, meeting_url)
        await self.notify_organizer_email(organizer, booking_event_payload, trigger_event, meeting_url)

    async def notify_client_email(
        self,
        attendee: BookingEventAttendee,
        booking_event_payload: BookingEventPayload,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        # TODO: Implement email sending logic when client templates are available
        # template = self.jinja_env.get_template("client_notification.html")
        # body = template.render(...)
        logger.info("Sending email to client (skeleton)", email=attendee.email, trigger_event=trigger_event)

    async def notify_client(
        self,
        booking_event_payload: BookingEventPayload,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None:
        for attendee in booking_event_payload.attendees:
            await self.notify_client_email(attendee, booking_event_payload, trigger_event, meeting_url)
