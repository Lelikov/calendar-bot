from __future__ import annotations
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    import datetime

    from app.dtos import BookingDTO, TriggerEvent, UserDTO


class INotificationController(Protocol):
    async def notify_organizer(
        self,
        user: UserDTO,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None: ...

    async def notify_organizer_telegram(
        self,
        *,
        user: UserDTO,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None: ...

    async def notify_client(
        self,
        booking: BookingDTO,
        trigger_event: TriggerEvent,
        meeting_url: str | None = None,
    ) -> None: ...

    async def notify_client_booking_rejected(
        self,
        *,
        booking: BookingDTO,
        available_from: datetime.datetime,
        previous_meeting_dates: list[datetime.datetime],
        rejection_type: str | None,
        active_booking_start: datetime.datetime | None,
    ) -> None: ...
