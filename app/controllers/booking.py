from asyncio import Task, create_task

import structlog
from aiogram import Bot

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.dtos import BookingEventDTO, BookingEventOrganizerDTO, TriggerEvent
from app.services.meeting import MeetingService
from app.services.notification import NotificationService


logger = structlog.get_logger(__name__)


class BookingController:
    def __init__(self, db: BookingDatabaseAdapter, shortener: UrlShortenerAdapter, bot: Bot) -> None:
        self.db = db
        self.meeting_service = MeetingService(db, shortener)
        self.notification_service = NotificationService(db, bot)
        self.background_tasks: set[Task] = set()
        self.client_meeting_prefix = "client_"

    async def _process_booking_flow(
        self,
        booking_event: BookingEventDTO,
        is_update_url_data: bool = False,
    ) -> None:
        booking_event_payload = booking_event.payload

        organizer_meeting_url = await self.meeting_service.setup_meeting(
            booking_event_payload=booking_event_payload,
            participant_name=booking_event_payload.organizer.name,
            is_update_url_data=is_update_url_data,
            is_update_url_in_db=True,
        )
        await self.notification_service.notify_organizer(
            organizer=booking_event_payload.organizer,
            booking_event_payload=booking_event_payload,
            trigger_event=booking_event.trigger_event,
            meeting_url=organizer_meeting_url,
        )

        client_meeting_url = await self.meeting_service.setup_meeting(
            booking_event_payload=booking_event_payload,
            participant_name=booking_event_payload.attendees[0].name,
            is_update_url_data=is_update_url_data,
            is_update_url_in_db=False,
            external_id_prefix=self.client_meeting_prefix,
        )
        await self.notification_service.notify_client(
            booking_event_payload=booking_event_payload,
            trigger_event=booking_event.trigger_event,
            meeting_url=client_meeting_url,
        )

    async def _handle_created(self, booking_event: BookingEventDTO) -> None:
        await self._process_booking_flow(booking_event=booking_event, is_update_url_data=False)

    async def _handle_rescheduled(self, booking_event: BookingEventDTO) -> None:
        await self._process_booking_flow(booking_event=booking_event, is_update_url_data=True)

    async def _handle_reassigned(self, booking_event: BookingEventDTO) -> None:
        booking_event_payload = booking_event.payload
        previous_organizer = booking_event_payload.organizer

        user = await self.db.get_user(email=booking_event_payload.new_organizer_email)

        current_organizer = BookingEventOrganizerDTO(
            name=user.name,
            email=user.email,
            time_zone=user.time_zone,
        )

        await self.notification_service.notify_organizer(
            organizer=previous_organizer,
            booking_event_payload=booking_event_payload,
            trigger_event=TriggerEvent.BOOKING_CANCELLED,
            meeting_url=None,
        )

        await self.notification_service.notify_organizer(
            organizer=current_organizer,
            booking_event_payload=booking_event_payload,
            trigger_event=TriggerEvent.BOOKING_CREATED,
            meeting_url=await self.meeting_service.setup_meeting(
                booking_event_payload=booking_event_payload,
                participant_name=current_organizer.name,
                is_update_url_data=True,
                is_update_url_in_db=True,
            ),
        )

    async def _handle_cancelled(self, booking_event: BookingEventDTO) -> None:
        booking_event_payload = booking_event.payload

        await self.notification_service.notify_organizer(
            organizer=booking_event_payload.organizer,
            booking_event_payload=booking_event_payload,
            trigger_event=booking_event.trigger_event,
            meeting_url=None,
        )
        await self.notification_service.notify_client(
            booking_event_payload=booking_event_payload,
            trigger_event=booking_event.trigger_event,
            meeting_url=None,
        )
        await self.meeting_service.delete_meeting(booking_event_payload=booking_event_payload)
        await self.meeting_service.delete_meeting(
            booking_event_payload=booking_event_payload,
            external_id_prefix=self.client_meeting_prefix,
        )

    async def _background_processing(self, booking_event: BookingEventDTO) -> None:
        logger.info("Processing booking event", uid=booking_event.payload.uid, type=booking_event.trigger_event)
        try:
            match booking_event.trigger_event:
                case TriggerEvent.BOOKING_CREATED:
                    await self._handle_created(booking_event)
                case TriggerEvent.BOOKING_RESCHEDULED:
                    await self._handle_rescheduled(booking_event)
                case TriggerEvent.BOOKING_PAYMENT_INITIATED:
                    await self._handle_reassigned(booking_event)
                case TriggerEvent.BOOKING_CANCELLED:
                    await self._handle_cancelled(booking_event)
                case _:
                    logger.warning("Unknown trigger event", event=booking_event.trigger_event)
        except Exception:
            logger.exception("Error in background processing", uid=booking_event.payload.uid)

    async def handle_booking(self, booking_event: BookingEventDTO) -> None:
        task = create_task(self._background_processing(booking_event))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
