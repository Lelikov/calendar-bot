from __future__ import annotations
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    import datetime

    from app.dtos import BookingDTO, BookingEventDTO, UserDTO


class IBookingDatabaseAdapter(Protocol):
    async def get_user_by_email(self, email: str) -> UserDTO | None: ...

    async def get_user_by_id(self, user_id: int) -> UserDTO | None: ...

    async def get_organizer_chat_id(self, email: str) -> int | None: ...

    async def get_booking(self, booking_uid: str) -> BookingDTO | None: ...

    async def update_booking_video_url(self, booking_uid: str, url: str) -> None: ...

    async def get_bookings(
        self,
        start_time_from: datetime.datetime,
        start_time_to: datetime.datetime,
    ) -> list[BookingDTO]: ...


class IBookingController(Protocol):
    async def handle_booking(self, booking_event: BookingEventDTO) -> None: ...

    async def handle_booking_reminder(self, start_time_from_shift: int, start_time_to_shift: int) -> int: ...
