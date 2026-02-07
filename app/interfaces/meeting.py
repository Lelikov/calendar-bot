from __future__ import annotations
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from app.dtos import BookingDTO, MeetWebhookEventDTO


class IMeetingController(Protocol):
    async def create_meeting_url(
        self,
        *,
        booking: BookingDTO,
        participant_id: str,
        participant_name: str,
        is_update_url_data: bool = False,
        is_update_url_in_db: bool = False,
        external_id_prefix: str = "",
    ) -> str: ...

    async def get_meeting_url(self, booking: BookingDTO, external_id_prefix: str = "") -> str | None: ...

    async def delete_meeting_url(
        self,
        *,
        booking: BookingDTO,
        external_id_prefix: str = "",
    ) -> None: ...


class IMeetWebhookController(Protocol):
    async def handle_webhook(self, event: MeetWebhookEventDTO) -> None: ...
