import datetime

from app.dtos import AttendeeBookingDTO, BookingDTO
from app.interfaces.booking_constraints import BookingConstraintsValidationResult, IBookingConstraintsAnalyzer


MIN_DAYS_BETWEEN_BOOKINGS = 7
MAX_BOOKINGS_PER_MONTH = 2
MAX_BOOKINGS_PER_YEAR = 10


class BookingConstraintsAnalyzer(IBookingConstraintsAnalyzer):
    def analyze_on_create(
        self,
        *,
        booking: BookingDTO,
        attendee_bookings: list[AttendeeBookingDTO],
    ) -> BookingConstraintsValidationResult:
        active_bookings = [
            attendee_booking for attendee_booking in attendee_bookings if not attendee_booking.bad_connection
        ]

        other_active_bookings = [
            attendee_booking for attendee_booking in active_bookings if attendee_booking.booking_uid != booking.uid
        ]

        available_dates: list[datetime.datetime] = [booking.start_time]

        nearest_future_booking = min(
            (
                attendee_booking
                for attendee_booking in other_active_bookings
                if attendee_booking.start_time > datetime.datetime.now(datetime.UTC)
            ),
            key=lambda attendee_booking: attendee_booking.start_time,
            default=None,
        )

        if nearest_future_booking:
            return {
                "is_allowed": False,
                "available_from": nearest_future_booking.end_time,
                "rejection_type": "has_active_booking",
                "active_booking_start": nearest_future_booking.start_time,
            }

        monthly_bookings = [
            attendee_booking
            for attendee_booking in active_bookings
            if attendee_booking.start_time.year == booking.start_time.year
            and attendee_booking.start_time.month == booking.start_time.month
        ]
        is_monthly_limit_violated = len(monthly_bookings) > MAX_BOOKINGS_PER_MONTH
        if is_monthly_limit_violated:
            available_dates.append(self._get_next_month_start(booking.start_time))

        yearly_bookings = [
            attendee_booking
            for attendee_booking in active_bookings
            if attendee_booking.start_time.year == booking.start_time.year
        ]
        is_yearly_limit_violated = len(yearly_bookings) > MAX_BOOKINGS_PER_YEAR
        if is_yearly_limit_violated:
            available_dates.append(
                booking.start_time.replace(year=booking.start_time.year + 1, month=1, day=1, hour=0, minute=0),
            )

        is_weekly_limit_violated = False
        for attendee_booking in other_active_bookings:
            days_delta = abs((booking.start_time - attendee_booking.start_time).days)
            if days_delta < MIN_DAYS_BETWEEN_BOOKINGS:
                is_weekly_limit_violated = True
                available_dates.append(attendee_booking.start_time + datetime.timedelta(days=MIN_DAYS_BETWEEN_BOOKINGS))

        if is_monthly_limit_violated or is_yearly_limit_violated or is_weekly_limit_violated:
            return {
                "is_allowed": False,
                "available_from": max(available_dates),
                "rejection_type": self._resolve_rejection_type(
                    is_monthly_limit_violated=is_monthly_limit_violated,
                    is_yearly_limit_violated=is_yearly_limit_violated,
                    is_weekly_limit_violated=is_weekly_limit_violated,
                ),
                "active_booking_start": None,
            }

        return {
            "is_allowed": True,
            "available_from": booking.start_time,
            "rejection_type": None,
            "active_booking_start": None,
        }

    @staticmethod
    def _get_next_month_start(target_date: datetime.datetime) -> datetime.datetime:
        if target_date.month == 12:
            return target_date.replace(year=target_date.year + 1, month=1, day=1, hour=0, minute=0)
        return target_date.replace(month=target_date.month + 1, day=1, hour=0, minute=0)

    @staticmethod
    def _resolve_rejection_type(
        *,
        is_monthly_limit_violated: bool,
        is_yearly_limit_violated: bool,
        is_weekly_limit_violated: bool,
    ) -> str | None:
        if is_monthly_limit_violated:
            return "month_limit"
        if is_yearly_limit_violated:
            return "year_limit"
        if is_weekly_limit_violated:
            return "min_interval"
        return None
