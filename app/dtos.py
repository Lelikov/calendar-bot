from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import TYPE_CHECKING, TypedDict


if TYPE_CHECKING:
    from datetime import datetime


class TriggerEvent(StrEnum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_PAYMENT_INITIATED = "BOOKING_PAYMENT_INITIATED"
    BOOKING_REMINDER = "BOOKING_REMINDER"
    PING = "PING"
    MEET_CLIENT_JOINED = "MEET_CLIENT_JOINED"


@dataclass(frozen=True, slots=True)
class BookingEventAttendeeDTO:
    name: str
    email: str
    time_zone: str


@dataclass(frozen=True, slots=True)
class BookingClientDTO:
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


@dataclass(frozen=True, slots=True)
class BookingAttendeeDTO:
    name: str
    email: str
    time_zone: str


class ResponseDTO(TypedDict):
    name: str
    email: str


@dataclass(slots=True)
class BookingDTO:
    created_at: datetime
    end_time: datetime
    ical_sequence: int
    id: int
    is_recorded: bool
    paid: bool
    responses: ResponseDTO
    start_time: datetime
    status: str
    title: str
    uid: str
    cancellation_reason: str | None = None
    cancelled_by: str | None = None
    custom_inputs: dict | None = None
    description: str | None = None
    destination_calendar_id: int | None = None
    dynamic_event_slug_ref: str | None = None
    dynamic_group_slug_ref: str | None = None
    event_type_id: int | None = None
    from_reschedule: str | None = None
    previous_booking: BookingDTO | None = None
    ical_uid: str | None = None
    idempotency_key: str | None = None
    location: str | None = None
    metadata: dict | None = None
    no_show_host: bool | None = None
    one_time_password: str | None = None
    rating: int | None = None
    rating_feedback: str | None = None
    reassign_by_id: int | None = None
    reassign_reason: str | None = None
    recurring_event_id: str | None = None
    rejection_reason: str | None = None
    rescheduled: bool | None = None
    rescheduled_by: str | None = None
    scheduled_jobs: list[str] | None = None
    sms_reminder_number: str | None = None
    updated_at: datetime | None = None
    user_id: int | None = None
    user_primary_email: str | None = None
    user: UserDTO | None = None
    client: BookingClientDTO | None = None


class MeetWebhookEventType(str, Enum):
    HANDLE_API_READY = "handleApiReady"
    VIDEO_CONFERENCE_JOINED = "videoConferenceJoined"
    VIDEO_CONFERENCE_LEFT = "videoConferenceLeft"


@dataclass(slots=True)
class MeetWebhookEventDTO:
    event: MeetWebhookEventType
    jwt: str
