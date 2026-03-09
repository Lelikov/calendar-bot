from enum import StrEnum
from typing import Any, Protocol


class EventType(StrEnum):
    BOOKING_REMINDER_SENT = "booking.reminder_sent"
    BOOKING_CREATED = "booking.created"
    BOOKING_RESCHEDULED = "booking.rescheduled"
    BOOKING_REASSIGNED = "booking.reassigned"
    BOOKING_CANCELLED = "booking.cancelled"
    MEETING_URL_CREATED = "meeting.url_created"
    MEETING_URL_DELETED = "meeting.url_deleted"
    NOTIFICATION_TELEGRAM_SENT = "notification.telegram.message_sent"
    NOTIFICATION_EMAIL_SENT = "notification.email.message_sent"


class IEventsAdapter(Protocol):
    async def send_event(self, booking_uid: str, event: EventType, data: dict[str, Any] | None = None) -> None: ...
