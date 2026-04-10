from __future__ import annotations
from typing import TYPE_CHECKING, Protocol, TypedDict


if TYPE_CHECKING:
    import datetime

    from app.dtos import AttendeeBookingDTO, BookingDTO


class BookingConstraintsValidationResult(TypedDict):
    is_allowed: bool
    available_from: datetime.datetime
    rejection_type: str | None  # "has_active_booking" | "month_limit" |
    # "year_limit" | "min_interval" | "cancelled_booking" | None
    active_booking_start: datetime.datetime | None


class IBookingConstraintsAnalyzer(Protocol):
    def analyze_on_create(
        self,
        *,
        booking: BookingDTO,
        attendee_bookings: list[AttendeeBookingDTO],
    ) -> BookingConstraintsValidationResult: ...
