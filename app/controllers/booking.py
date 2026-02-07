import datetime
import json
from asyncio import Task, create_task

import structlog

from app.dtos import BookingDTO, BookingEventDTO, TriggerEvent
from app.interfaces.booking import IBookingDatabaseAdapter
from app.interfaces.chat import IChatController
from app.interfaces.meeting import IMeetingController
from app.interfaces.notification import INotificationController
from app.interfaces.url_shortener import IUrlShortener


logger = structlog.get_logger(__name__)


class BookingController:
    def __init__(
        self,
        db: IBookingDatabaseAdapter,
        shortener: IUrlShortener,
        chat_controller: IChatController,
        meeting_controller: IMeetingController,
        notification_controller: INotificationController,
    ) -> None:
        self.db = db
        self.shortener = shortener
        self.chat_controller = chat_controller
        self.meeting_controller = meeting_controller
        self.notification_controller = notification_controller
        self.background_tasks: set[Task] = set()
        self.client_meeting_prefix = "client_"
        self.reminder_sent: set[str] = set()

    async def handle_booking(self, booking_event: BookingEventDTO) -> None:
        task = create_task(self._background_processing(booking_event))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def handle_booking_reminder(self, start_time_from_shift: int, start_time_to_shift: int) -> int:
        bookings = await self.db.get_bookings(
            start_time_from=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=start_time_from_shift),
            start_time_to=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=start_time_to_shift),
        )
        count_sent_reminders = 0
        for booking in bookings:
            if booking.uid in self.reminder_sent:
                continue
            self.reminder_sent.add(booking.uid)
            if "cloud" in booking.metadata:
                meeting_url = json.loads(booking.metadata).get("videoCallUrl")
            else:
                meeting_url = await self.meeting_controller.get_meeting_url(
                    booking=booking,
                    external_id_prefix=self.client_meeting_prefix,
                )
            await self.notification_controller.notify_client(
                booking=booking,
                meeting_url=meeting_url,
                trigger_event=TriggerEvent.BOOKING_REMINDER,
            )
            count_sent_reminders += 1
        return count_sent_reminders

    async def _process_booking_flow(
        self,
        booking_event: BookingEventDTO,
        is_update_url_data: bool = False,
    ) -> None:
        booking: BookingDTO = await self.db.get_booking(booking_event.payload.uid)
        if not booking:
            logger.warning("Booking not found", uid=booking_event.payload.uid)
            return None

        try:
            await self.chat_controller.create_chat(
                channel_id=booking.uid,
                organizer_id=booking.user.email,
                client_id=booking.client.email,
            )
        except Exception:
            logger.exception("Error while creating chat", uid=booking_event.payload.uid)

        if booking.from_reschedule:
            booking.previous_booking = await self.db.get_booking(booking.from_reschedule)
            try:
                await self.chat_controller.delete_chat(channel_id=booking.previous_booking.uid)
            except Exception:
                logger.exception("Error while deleting chat for previous booking", uid=booking.uid)

        organizer_meeting_url = await self.meeting_controller.create_meeting_url(
            booking=booking,
            participant_id=booking.user.email,
            participant_name=booking.user.name,
            is_update_url_data=is_update_url_data,
            is_update_url_in_db=True,
        )
        await self.notification_controller.notify_organizer(
            user=booking.user,
            booking=booking,
            trigger_event=booking_event.trigger_event,
            meeting_url=organizer_meeting_url,
        )

        client_meeting_url = await self.meeting_controller.create_meeting_url(
            booking=booking,
            participant_id=booking.client.email,
            participant_name=booking.client.name,
            is_update_url_data=is_update_url_data,
            is_update_url_in_db=False,
            external_id_prefix=self.client_meeting_prefix,
        )
        await self.notification_controller.notify_client(
            booking=booking,
            trigger_event=booking_event.trigger_event,
            meeting_url=client_meeting_url,
        )
        return None

    async def _handle_created(self, booking_event: BookingEventDTO) -> None:
        await self._process_booking_flow(booking_event=booking_event, is_update_url_data=False)

    async def _handle_rescheduled(self, booking_event: BookingEventDTO) -> None:
        await self._process_booking_flow(booking_event=booking_event, is_update_url_data=True)

    async def _handle_reassigned(self, booking_event: BookingEventDTO) -> None:
        booking = await self.db.get_booking(booking_event.payload.uid)
        if previous_organizer := await self.db.get_user_by_id(user_id=booking.reassign_by_id):
            await self.notification_controller.notify_organizer(
                user=previous_organizer,
                booking=booking,
                trigger_event=TriggerEvent.BOOKING_CANCELLED,
                meeting_url=None,
            )
        try:
            await self.chat_controller.delete_chat(channel_id=booking.uid)
            await self.chat_controller.create_chat(
                channel_id=booking.uid,
                organizer_id=booking.user.email,
                client_id=booking.client.email,
            )
        except Exception:
            logger.exception("Error while deleting chat for booking", uid=booking.uid)

        if booking.from_reschedule:
            booking.from_reschedule = None

        meeting_url = await self.meeting_controller.create_meeting_url(
            booking=booking,
            participant_id=booking.user.email,
            participant_name=booking.user.name,
            is_update_url_data=True,
            is_update_url_in_db=True,
        )
        await self.notification_controller.notify_organizer(
            user=booking.user,
            booking=booking,
            trigger_event=TriggerEvent.BOOKING_CREATED,
            meeting_url=meeting_url,
        )

    async def _handle_cancelled(self, booking_event: BookingEventDTO) -> None:
        booking = await self.db.get_booking(booking_event.payload.uid)

        await self.notification_controller.notify_organizer(
            user=booking.user,
            booking=booking,
            trigger_event=booking_event.trigger_event,
            meeting_url=None,
        )
        await self.notification_controller.notify_client(
            booking=booking,
            trigger_event=booking_event.trigger_event,
            meeting_url=None,
        )
        try:
            await self.chat_controller.delete_chat(channel_id=booking.uid)
        except Exception:
            logger.exception("Error while deleting chat for booking", uid=booking.uid)
        await self.meeting_controller.delete_meeting_url(booking=booking)
        await self.meeting_controller.delete_meeting_url(booking=booking, external_id_prefix=self.client_meeting_prefix)

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
