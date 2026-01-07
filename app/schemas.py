from enum import StrEnum

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel


class BaseCalComModel(BaseModel):
    class Config:
        alias_generator = to_camel
        populate_by_name = True


class BookingEventAttendee(BaseCalComModel):
    name: str
    email: str
    time_zone: str


class BookingEventOrganizer(BaseCalComModel):
    name: str
    email: str
    time_zone: str


class BookingEventPayload(BaseCalComModel):
    attendees: list[BookingEventAttendee]
    description: str | None = None
    end_time: str
    organizer: BookingEventOrganizer
    start_time: str
    title: str
    uid: str
    cancellation_reason: str | None = None
    new_organizer_email: str | None = Field(default=None, alias="rescheduledBy")
    reschedule_end_time: str | None = None
    reschedule_start_time: str | None = None
    reschedule_uid: str | None = None


class TriggerEvent(StrEnum):
    BOOKING_CREATED = "BOOKING_CREATED"
    BOOKING_RESCHEDULED = "BOOKING_RESCHEDULED"
    BOOKING_CANCELLED = "BOOKING_CANCELLED"
    BOOKING_PAYMENT_INITIATED = "BOOKING_PAYMENT_INITIATED"
    PING = "PING"


class BookingEvent(BaseCalComModel):
    payload: BookingEventPayload
    trigger_event: TriggerEvent
