from typing import Literal

from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from app.dtos import (
    BookingEventAttendeeDTO,
    BookingEventDTO,
    BookingEventOrganizerDTO,
    BookingEventPayloadDTO,
    MailWebhookDeliveryInfoDTO,
    MailWebhookEventDataDTO,
    MailWebhookEventDTO,
    MailWebhookEventsByUserDTO,
    MailWebhookUserEventDTO,
    MeetWebhookEventDTO,
    TriggerEvent,
)


class BaseCalComModel(BaseModel):
    class Config:
        alias_generator = to_camel
        populate_by_name = True


class BookingReminderBody(BaseModel):
    start_time_from_shift: int = Field(default=23)
    start_time_to_shift: int = Field(default=24)
    booking_uid: str | None = None


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


class MailWebhookDeliveryInfo(BaseModel):
    delivery_status: str
    destination_response: str

    def to_dto(self) -> MailWebhookDeliveryInfoDTO:
        return MailWebhookDeliveryInfoDTO(
            delivery_status=self.delivery_status,
            destination_response=self.destination_response,
        )


class MailWebhookEventData(BaseModel):
    job_id: str
    email: str
    status: str
    event_time: str
    delivery_info: MailWebhookDeliveryInfo

    def to_dto(self) -> MailWebhookEventDataDTO:
        return MailWebhookEventDataDTO(
            job_id=self.job_id,
            email=self.email,
            status=self.status,
            event_time=self.event_time,
            delivery_info=self.delivery_info.to_dto(),
        )


class MailWebhookUserEvent(BaseModel):
    event_name: str
    event_data: MailWebhookEventData

    def to_dto(self) -> MailWebhookUserEventDTO:
        return MailWebhookUserEventDTO(
            event_name=self.event_name,
            event_data=self.event_data.to_dto(),
        )


class MailWebhookEventsByUser(BaseModel):
    user_id: int
    events: list[MailWebhookUserEvent]

    def to_dto(self) -> MailWebhookEventsByUserDTO:
        return MailWebhookEventsByUserDTO(
            user_id=self.user_id,
            events=[event.to_dto() for event in self.events],
        )


class MailWebhookEvent(BaseModel):
    auth: str
    events_by_user: list[MailWebhookEventsByUser]

    def to_dto(self) -> MailWebhookEventDTO:
        return MailWebhookEventDTO(
            auth=self.auth,
            events_by_user=[event.to_dto() for event in self.events_by_user],
        )


class JitsiWebhookEvent(BaseModel):
    event: Literal["handleApiReady", "videoConferenceJoined", "videoConferenceLeft"]
    jwt: str
    payload: dict

    class Config:
        alias_generator = to_camel

    def to_dto(self) -> MeetWebhookEventDTO:
        return MeetWebhookEventDTO(
            event=self.event,
            jwt=self.jwt,
        )
