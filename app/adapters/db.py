import datetime
from datetime import UTC

from databases import Database
from databases.interfaces import Record

from app.dtos import BookingClientDTO, BookingDTO, UserDTO


class BookingDatabaseAdapter:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def get_user_by_email(self, email: str) -> UserDTO | None:
        async with Database(self.dsn) as database:
            row = await database.fetch_one(query="SELECT * FROM users WHERE email = :email", values={"email": email})

        if not row:
            return None

        return UserDTO(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            locked=row["locked"],
            time_zone=row["timeZone"],
            telegram_chat_id=row["telegram_chat_id"],
            telegram_token=row["telegram_token"],
        )

    async def get_user_by_id(self, user_id: int) -> UserDTO | None:
        async with Database(self.dsn) as database:
            row = await database.fetch_one(query="SELECT * FROM users WHERE id = :user_id", values={"user_id": user_id})

        if not row:
            return None

        return UserDTO(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            locked=row["locked"],
            time_zone=row["timeZone"],
            telegram_chat_id=row["telegram_chat_id"],
            telegram_token=row["telegram_token"],
        )

    async def get_organizer_chat_id(self, email: str) -> int | None:
        async with Database(self.dsn) as database:
            query = (
                "SELECT telegram_chat_id FROM users "
                "WHERE locked = FALSE "
                "AND email = :email "
                "AND telegram_chat_id IS NOT NULL"
            )
            row = await database.fetch_one(query=query, values={"email": email})
        if row:
            return row["telegram_chat_id"]
        return None

    async def get_booking(self, booking_uid: str) -> BookingDTO | None:
        async with Database(self.dsn) as database:
            query = """
                SELECT
                    b.*,
                    u.id as user_id_val, u.name as user_name, u.email as user_email, u.locked as user_locked,
                    u."timeZone" as user_time_zone, u.telegram_chat_id as user_telegram_chat_id,
                    u.telegram_token as user_telegram_token,
                    a.name as client_name, a.email as client_email, a."timeZone" as client_time_zone
                FROM public."Booking" b
                LEFT JOIN users u ON b."userId" = u.id
                LEFT JOIN "Attendee" a ON a."bookingId" = b.id
                WHERE b.uid = :booking_uid
            """
            row = await database.fetch_one(query=query, values={"booking_uid": booking_uid})
            if row:
                return self._fill_booking_dto(row)
            return None

    async def update_booking_video_url(self, booking_uid: str, url: str) -> None:
        async with Database(self.dsn) as database:
            query = """
                UPDATE public."Booking"
                SET metadata = COALESCE(metadata, '{}'::jsonb) ||
                               jsonb_build_object('videoCallUrl', CAST(:url AS text))
                WHERE uid = :booking_uid
                    """
            await database.execute(query=query, values={"booking_uid": booking_uid, "url": url})

    async def get_bookings(
        self,
        start_time_from: datetime.datetime,
        start_time_to: datetime.datetime,
    ) -> list[BookingDTO]:
        async with Database(self.dsn) as database:
            query = """
                SELECT
                    b.*,
                    u.id as user_id_val, u.name as user_name, u.email as user_email, u.locked as user_locked,
                    u."timeZone" as user_time_zone, u.telegram_chat_id as user_telegram_chat_id,
                    u.telegram_token as user_telegram_token,
                    a.name as client_name, a.email as client_email, a."timeZone" as client_time_zone
                FROM public."Booking" b
                LEFT JOIN users u ON b."userId" = u.id
                LEFT JOIN "Attendee" a ON a."bookingId" = b.id
                WHERE b.status = 'accepted'
                    AND b."startTime" BETWEEN
                :start_time_from
                AND
                :start_time_to
            """
            rows = await database.fetch_all(
                query=query,
                values={
                    "start_time_from": start_time_from.astimezone(UTC).replace(tzinfo=None),
                    "start_time_to": start_time_to.astimezone(UTC).replace(tzinfo=None),
                },
            )
        return [self._fill_booking_dto(row) for row in rows]

    @staticmethod
    def _fill_booking_dto(row: Record) -> BookingDTO:
        user = UserDTO(
            id=row["user_id_val"],
            name=row["user_name"],
            email=row["user_email"],
            locked=row["user_locked"],
            time_zone=row["user_time_zone"],
            telegram_chat_id=row["user_telegram_chat_id"],
            telegram_token=row["user_telegram_token"],
        )

        client = BookingClientDTO(
            name=row["client_name"],
            email=row["client_email"],
            time_zone=row["client_time_zone"],
        )

        return BookingDTO(
            id=row["id"],
            uid=row["uid"],
            user_id=row["userId"],
            event_type_id=row["eventTypeId"],
            title=row["title"],
            description=row["description"],
            start_time=row["startTime"].replace(tzinfo=UTC),
            end_time=row["endTime"].replace(tzinfo=UTC),
            created_at=row["createdAt"],
            updated_at=row["updatedAt"],
            location=row["location"],
            paid=row["paid"],
            status=row["status"],
            cancellation_reason=row["cancellationReason"],
            rejection_reason=row["rejectionReason"],
            from_reschedule=row["fromReschedule"],
            rescheduled=row["rescheduled"],
            dynamic_event_slug_ref=row["dynamicEventSlugRef"],
            dynamic_group_slug_ref=row["dynamicGroupSlugRef"],
            recurring_event_id=row["recurringEventId"],
            custom_inputs=row["customInputs"],
            sms_reminder_number=row["smsReminderNumber"],
            destination_calendar_id=row["destinationCalendarId"],
            scheduled_jobs=row["scheduledJobs"],
            metadata=row["metadata"],
            responses=row["responses"],
            is_recorded=row["isRecorded"],
            ical_sequence=row["iCalSequence"],
            ical_uid=row["iCalUID"],
            user_primary_email=row["userPrimaryEmail"],
            idempotency_key=row["idempotencyKey"],
            no_show_host=row["noShowHost"],
            rating=row["rating"],
            rating_feedback=row["ratingFeedback"],
            cancelled_by=row["cancelledBy"],
            rescheduled_by=row["rescheduledBy"],
            one_time_password=row["oneTimePassword"],
            reassign_reason=row["reassignReason"],
            reassign_by_id=row["reassignById"],
            user=user,
            client=client,
        )
