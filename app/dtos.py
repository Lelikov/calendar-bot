from dataclasses import dataclass
from enum import StrEnum


class TriggerEvent(StrEnum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_PAYMENT_INITIATED = "BOOKING_PAYMENT_INITIATED"
    PING = "PING"


@dataclass(frozen=True, slots=True)
class BookingEventAttendeeDTO:
    name: str
    email: str
    time_zone: str


@dataclass(frozen=True, slots=True)
class BookingEventOrganizerDTO:
    name: str
    email: str
    time_zone: str


@dataclass(frozen=True, slots=True)
class BookingEventPayloadDTO:
    attendees: list[BookingEventAttendeeDTO]
    end_time: str
    organizer: BookingEventOrganizerDTO
    start_time: str
    title: str
    uid: str
    description: str | None = None
    cancellation_reason: str | None = None
    new_organizer_email: str | None = None
    reschedule_end_time: str | None = None
    reschedule_start_time: str | None = None
    reschedule_uid: str | None = None


@dataclass(frozen=True, slots=True)
class BookingEventDTO:
    payload: BookingEventPayloadDTO
    trigger_event: TriggerEvent


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: int
    name: str
    email: str
    locked: bool
    time_zone: str
    telegram_chat_id: int | None = None
    telegram_token: str | None = None


@dataclass(frozen=True, slots=True)
class MailWebhookMessageDTO:
    direction: str
    from_email: str
    id: int
    message_id: str
    spam_status: str
    subject: str
    timestamp: float
    to: str
    token: str
    tag: str | None = None


@dataclass(frozen=True, slots=True)
class MailWebhookPayloadDTO:
    details: str
    message: MailWebhookMessageDTO
    output: str
    sent_with_ssl: bool
    status: str
    time: float
    timestamp: float


@dataclass(frozen=True, slots=True)
class MailWebhookEventDTO:
    event: str
    payload: MailWebhookPayloadDTO
    timestamp: float
    uuid: str
