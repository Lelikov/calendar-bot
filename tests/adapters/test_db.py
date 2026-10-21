import datetime
from typing import Any

from app.adapters.db import BookingDatabaseAdapter


BASE_BOOKING_ROW: dict[str, Any] = {
    "id": 1,
    "uid": "booking-uid",
    "userId": 10,
    "eventTypeId": 100,
    "title": "Consultation",
    "description": None,
    # Naive on purpose: asyncpg returns tz-naive UTC rows and the adapter attaches
    # tzinfo itself (see _fill_booking_dto).
    "startTime": datetime.datetime(2026, 1, 1, 12, 0),  # noqa: DTZ001
    "endTime": datetime.datetime(2026, 1, 1, 13, 0),  # noqa: DTZ001
    "createdAt": datetime.datetime(2026, 1, 1, 11, 0),  # noqa: DTZ001
    "updatedAt": None,
    "location": None,
    "paid": True,
    "status": "accepted",
    "cancellationReason": None,
    "rejectionReason": None,
    "fromReschedule": None,
    "rescheduled": None,
    "dynamicEventSlugRef": None,
    "dynamicGroupSlugRef": None,
    "recurringEventId": None,
    "customInputs": None,
    "smsReminderNumber": None,
    "destinationCalendarId": None,
    "scheduledJobs": None,
    "metadata": None,
    "responses": {"name": "Client", "email": "client@example.test"},
    "isRecorded": False,
    "iCalSequence": 0,
    "iCalUID": None,
    "userPrimaryEmail": None,
    "idempotencyKey": None,
    "noShowHost": None,
    "rating": None,
    "ratingFeedback": None,
    "cancelledBy": None,
    "rescheduledBy": None,
    "oneTimePassword": None,
    "reassignReason": None,
    "reassignById": None,
    "user_id_val": 10,
    "user_name": "Jane Doe",
    "user_email": "jane@example.test",
    "user_locked": False,
    "user_time_zone": "Europe/Moscow",
    "user_telegram_chat_id": None,
    "user_telegram_token": None,
    "user_username": "jane-doe",
    "event_type_slug": "consultation",
    "event_type_parent_id": 42,
    "client_name": "Client",
    "client_email": "client@example.test",
    "client_time_zone": "Europe/Moscow",
}


class FakeSqlExecutor:
    def __init__(self, *, fetch_one_result: dict | None = None, fetch_all_result: list[dict] | None = None) -> None:
        self.fetch_one_result = fetch_one_result
        self.fetch_all_result = fetch_all_result or []
        self.fetch_one_calls: list[tuple[str, dict]] = []
        self.fetch_all_calls: list[tuple[str, dict]] = []

    async def fetch_one(self, query: str, values: dict) -> dict | None:
        self.fetch_one_calls.append((query, values))
        return self.fetch_one_result

    async def fetch_all(self, query: str, values: dict) -> list[dict]:
        self.fetch_all_calls.append((query, values))
        return self.fetch_all_result

    async def execute(self, query: str, values: dict) -> None:
        raise NotImplementedError

    async def execute_returning(self, query: str, values: dict) -> dict | None:
        raise NotImplementedError

    async def execute_in_transaction(self, statements: list[tuple[str, dict]]) -> None:
        raise NotImplementedError


class TestGetBooking:
    async def test_returns_event_type_and_organizer_username_for_tariff_detection(self) -> None:
        sql = FakeSqlExecutor(fetch_one_result=dict(BASE_BOOKING_ROW))
        adapter = BookingDatabaseAdapter(sql)

        booking = await adapter.get_booking("booking-uid")

        assert booking is not None
        assert booking.event_type_slug == "consultation"
        assert booking.event_type_parent_id == 42
        assert booking.user is not None
        assert booking.user.username == "jane-doe"

    async def test_query_joins_event_type_and_selects_username(self) -> None:
        sql = FakeSqlExecutor(fetch_one_result=dict(BASE_BOOKING_ROW))
        adapter = BookingDatabaseAdapter(sql)

        await adapter.get_booking("booking-uid")

        query, _values = sql.fetch_one_calls[0]
        assert '"EventType"' in query
        assert "u.username" in query

    async def test_returns_none_when_booking_not_found(self) -> None:
        sql = FakeSqlExecutor(fetch_one_result=None)
        adapter = BookingDatabaseAdapter(sql)

        booking = await adapter.get_booking("missing-uid")

        assert booking is None


class TestGetBookings:
    async def test_fills_event_type_and_username_for_each_booking(self) -> None:
        other_row = dict(BASE_BOOKING_ROW)
        other_row.update(
            {
                "uid": "social-booking-uid",
                "event_type_slug": "volunteer-psychologist",
                "event_type_parent_id": None,
                "user_username": None,
            },
        )
        sql = FakeSqlExecutor(fetch_all_result=[dict(BASE_BOOKING_ROW), other_row])
        adapter = BookingDatabaseAdapter(sql)

        bookings = await adapter.get_bookings(
            datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            datetime.datetime(2026, 1, 2, tzinfo=datetime.UTC),
        )

        commercial, social = bookings
        assert commercial.event_type_slug == "consultation"
        assert commercial.event_type_parent_id == 42
        assert commercial.user is not None
        assert commercial.user.username == "jane-doe"

        assert social.event_type_slug == "volunteer-psychologist"
        assert social.event_type_parent_id is None
        assert social.user is not None
        assert social.user.username is None
