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
        has_active_booking: bool,
        previous_meeting_dates: list[datetime.datetime],
        active_booking_start: datetime.datetime | None,
        rejection_reasons: list[str],
    ) -> None: ...
