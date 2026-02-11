import datetime

import structlog

from app.dtos import AttendeeBookingDTO, BookingDTO, BookingEventDTO, TriggerEvent
from app.interfaces.booking import IBookingDatabaseAdapter
from app.interfaces.chat import IChatController
from app.interfaces.meeting import IMeetingController, INotificationStateController
from app.interfaces.notification import INotificationController
from app.interfaces.url_shortener import IUrlShortener


logger = structlog.get_logger(__name__)


BOOKING_REMINDER_NOTIFICATION_KEY = "booking_reminder_notified"
BOOKING_REMINDER_TTL_SECONDS = 60 * 60 * 24
MIN_DAYS_BETWEEN_BOOKINGS = 7
MAX_BOOKINGS_PER_MONTH = 2
MAX_BOOKINGS_PER_YEAR = 10
INACTIVE_BOOKING_STATUSES = {"cancelled", "rejected"}


class BookingController:
    def __init__(
        self,
        db: IBookingDatabaseAdapter,
        shortener: IUrlShortener,
        chat_controller: IChatController,
        meeting_controller: IMeetingController,
        notification_controller: INotificationController,
        notification_state_controller: INotificationStateController,
    ) -> None:
        self.db = db
        self.shortener = shortener
        self.chat_controller = chat_controller
        self.meeting_controller = meeting_controller
        self.notification_controller = notification_controller
        self.notification_state_controller = notification_state_controller
        self.client_meeting_prefix = "client_"

    async def handle_booking(self, booking_event: BookingEventDTO) -> None:
        await self._background_processing(booking_event)

    async def handle_booking_reminder(
        self,
        start_time_from_shift: int,
        start_time_to_shift: int,
        booking_uid: str,
    ) -> int:
        bookings = (
            [await self.db.get_booking(booking_uid)]
            if booking_uid
            else await self.db.get_bookings(
                start_time_from=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=start_time_from_shift),
                start_time_to=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=start_time_to_shift),
            )
        )
        count_sent_reminders = 0
        for booking in bookings:
            if await self.notification_state_controller.was_notified(
                room=f"{booking.uid}{booking.client.email}",
                key=BOOKING_REMINDER_NOTIFICATION_KEY,
            ):
                continue

            meeting_url = await self.meeting_controller.get_meeting_url(
                booking=booking,
                external_id_prefix=self.client_meeting_prefix,
            )
            await self.notification_controller.notify_client(
                booking=booking,
                meeting_url=meeting_url,
                trigger_event=TriggerEvent.BOOKING_REMINDER,
            )
            await self.notification_state_controller.mark_notified(
                room=f"{booking.uid}{booking.client.email}",
                ttl_seconds=BOOKING_REMINDER_TTL_SECONDS,
                key=BOOKING_REMINDER_NOTIFICATION_KEY,
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

    async def _validate_booking_constraints_on_create(self, booking_uid: str) -> bool:
        booking = await self.db.get_booking(booking_uid)
        if not booking:
            logger.warning("Booking not found while validating constraints", uid=booking_uid)
            return False

        attendee_bookings = await self.db.get_attendee_bookings_by_email(email=booking.client.email)
        validation_result = self._analyze_booking_constraints(
            booking=booking,
            attendee_bookings=attendee_bookings,
        )
        if validation_result["is_allowed"]:
            return True

        previous_meeting_dates = sorted(
            [
                attendee_booking.start_time
                for attendee_booking in attendee_bookings
                if attendee_booking.booking_uid != booking.uid
                and attendee_booking.start_time.date() <= booking.start_time.date()
            ],
        )

        await self.notification_controller.notify_client_booking_rejected(
            booking=booking,
            available_from=validation_result["available_from"],
            has_active_booking=validation_result["has_active_booking"],
            previous_meeting_dates=previous_meeting_dates,
            active_booking_start=validation_result["active_booking_start"],
        )

        await self.db.delete_booking_and_attendee_by_booking_id(booking_id=booking.id)
        logger.warning(
            "Booking was deleted due to booking rules violation",
            uid=booking.uid,
            booking_id=booking.id,
            client_email=booking.client.email,
        )
        return False

    @staticmethod
    def _analyze_booking_constraints(booking: BookingDTO, attendee_bookings: list[AttendeeBookingDTO]) -> dict:
        now_utc = datetime.datetime.now(datetime.UTC)
        active_bookings = [
            attendee_booking
            for attendee_booking in attendee_bookings
            if attendee_booking.status.lower() not in INACTIVE_BOOKING_STATUSES
        ]

        other_active_bookings = [
            attendee_booking for attendee_booking in active_bookings if attendee_booking.booking_uid != booking.uid
        ]

        available_dates: list[datetime.datetime] = [booking.start_time]

        nearest_future_booking = min(
            (attendee_booking for attendee_booking in other_active_bookings if attendee_booking.start_time > now_utc),
            key=lambda attendee_booking: attendee_booking.start_time,
            default=None,
        )

        if nearest_future_booking:
            return {
                "is_allowed": False,
                "available_from": nearest_future_booking.end_time,
                "has_active_booking": True,
                "active_booking_start": nearest_future_booking.start_time,
            }

        monthly_bookings = [
            attendee_booking
            for attendee_booking in active_bookings
            if attendee_booking.start_time.year == booking.start_time.year
            and attendee_booking.start_time.month == booking.start_time.month
        ]
        if len(monthly_bookings) > MAX_BOOKINGS_PER_MONTH:
            if booking.start_time.month == 12:
                available_dates.append(
                    booking.start_time.replace(year=booking.start_time.year + 1, month=1, day=1, hour=0, minute=0),
                )
            else:
                available_dates.append(
                    booking.start_time.replace(month=booking.start_time.month + 1, day=1, hour=0, minute=0),
                )

        yearly_bookings = [
            attendee_booking
            for attendee_booking in active_bookings
            if attendee_booking.start_time.year == booking.start_time.year
        ]
        if len(yearly_bookings) > MAX_BOOKINGS_PER_YEAR:
            available_dates.append(
                booking.start_time.replace(year=booking.start_time.year + 1, month=1, day=1, hour=0, minute=0),
            )

        is_weekly_limit_violated = False
        for attendee_booking in other_active_bookings:
            days_delta = abs((booking.start_time - attendee_booking.start_time).days)
            if days_delta < MIN_DAYS_BETWEEN_BOOKINGS:
                is_weekly_limit_violated = True
                available_dates.append(attendee_booking.start_time + datetime.timedelta(days=MIN_DAYS_BETWEEN_BOOKINGS))

        is_limits_violated = (
            len(monthly_bookings) > MAX_BOOKINGS_PER_MONTH
            or len(yearly_bookings) > MAX_BOOKINGS_PER_YEAR
            or is_weekly_limit_violated
        )
        if is_limits_violated:
            return {
                "is_allowed": False,
                "available_from": max(available_dates),
                "has_active_booking": False,
                "active_booking_start": None,
            }

        return {
            "is_allowed": True,
            "available_from": booking.start_time,
            "has_active_booking": False,
            "active_booking_start": None,
        }

    async def _handle_created(self, booking_event: BookingEventDTO) -> None:
        if not await self._validate_booking_constraints_on_create(booking_uid=booking_event.payload.uid):
            return None

        await self._process_booking_flow(booking_event=booking_event, is_update_url_data=False)
        return None

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
