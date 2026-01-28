from pydantic import BaseModel, Field
from pydantic.alias_generators import to_camel

from app.dtos import (
    BookingEventAttendeeDTO,
    BookingEventDTO,
    BookingEventOrganizerDTO,
    BookingEventPayloadDTO,
    MailWebhookEventDTO,
    MailWebhookMessageDTO,
    MailWebhookPayloadDTO,
    TriggerEvent,
)


class BaseCalComModel(BaseModel):
    class Config:
        alias_generator = to_camel
        populate_by_name = True


class BookingReminderBody(BaseModel):
    start_time_from_shift: int = 23
    start_time_to_shift: int = 24


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


class MailWebhookMessage(BaseModel):
    direction: str
    from_email: str = Field(alias="from")
    id: int
    message_id: str
    spam_status: str
    subject: str
    tag: str | None
    timestamp: float
    to: str
    token: str

    def to_dto(self) -> MailWebhookMessageDTO:
        return MailWebhookMessageDTO(
            direction=self.direction,
            from_email=self.from_email,
            id=self.id,
            message_id=self.message_id,
            spam_status=self.spam_status,
            subject=self.subject,
            tag=self.tag,
            timestamp=self.timestamp,
            to=self.to,
            token=self.token,
        )


class MailWebhookPayload(BaseModel):
    details: str
    message: MailWebhookMessage
    output: str
    sent_with_ssl: bool
    status: str
    time: float
    timestamp: float

    def to_dto(self) -> MailWebhookPayloadDTO:
        return MailWebhookPayloadDTO(
            details=self.details,
            message=self.message.to_dto(),
            output=self.output,
            sent_with_ssl=self.sent_with_ssl,
            status=self.status,
            time=self.time,
            timestamp=self.timestamp,
        )


class MailWebhookEvent(BaseModel):
    event: str
    payload: MailWebhookPayload
    timestamp: float
    uuid: str

    def to_dto(self) -> MailWebhookEventDTO:
        return MailWebhookEventDTO(
            event=self.event,
            payload=self.payload.to_dto(),
            timestamp=self.timestamp,
            uuid=self.uuid,
        )
