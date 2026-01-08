from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from app.dtos import (
    BookingEventAttendeeDTO,
    BookingEventDTO,
    BookingEventOrganizerDTO,
    BookingEventPayloadDTO,
    TriggerEvent,
)


class BaseCalComModel(BaseModel):
    class Config:
        alias_generator = to_camel
        populate_by_name = True


class BookingEventAttendee(BaseCalComModel):
    name: str
    email: str
    time_zone: str

    def to_dto(self) -> BookingEventAttendeeDTO:
        return BookingEventAttendeeDTO(
            name=self.name,
            email=self.email,
            time_zone=self.time_zone,
        )


class BookingEventOrganizer(BaseCalComModel):
    name: str
    email: str
    time_zone: str

    def to_dto(self) -> BookingEventOrganizerDTO:
        return BookingEventOrganizerDTO(
            name=self.name,
            email=self.email,
            time_zone=self.time_zone,
        )


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

    def to_dto(self) -> BookingEventPayloadDTO:
        return BookingEventPayloadDTO(
            attendees=[attendee.to_dto() for attendee in self.attendees],
            description=self.description,
            end_time=self.end_time,
            organizer=self.organizer.to_dto(),
            start_time=self.start_time,
            title=self.title,
            uid=self.uid,
            cancellation_reason=self.cancellation_reason,
            new_organizer_email=self.new_organizer_email,
            reschedule_end_time=self.reschedule_end_time,
            reschedule_start_time=self.reschedule_start_time,
            reschedule_uid=self.reschedule_uid,
        )


class BookingEvent(BaseCalComModel):
    payload: BookingEventPayload
    trigger_event: TriggerEvent

    def to_dto(self) -> BookingEventDTO:
        return BookingEventDTO(
            payload=self.payload.to_dto(),
            trigger_event=self.trigger_event,
        )
