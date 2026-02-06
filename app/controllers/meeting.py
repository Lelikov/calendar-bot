import time
from asyncio import sleep
from datetime import datetime

import jwt
import structlog

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.controllers.chat import ChatController
from app.dtos import BookingDTO
from app.settings import Settings


logger = structlog.get_logger(__name__)

METADATA_WAIT_ATTEMPTS = 1
METADATA_WAIT_DELAY = 5


class MeetingController:
    def __init__(
        self,
        db: BookingDatabaseAdapter,
        shortener: UrlShortenerAdapter,
        chat_controller: ChatController,
        settings: Settings,
    ) -> None:
        self.db = db
        self.shortener = shortener
        self.chat_controller = chat_controller
        self.settings = settings
        self.timeshift = 5 * 60

    async def create_meeting_url(
        self,
        *,
        booking: BookingDTO,
        participant_id: str,
        participant_name: str,
        is_update_url_data: bool = False,
        is_update_url_in_db: bool = False,
        external_id_prefix: str = "",
    ) -> str:
        participant_video_token = self._create_jitsi_token(
            booking=booking,
            participant_name=participant_name,
            external_id_prefix=external_id_prefix,
        )
        participant_chat_token = self.chat_controller.create_token(
            user_id=participant_id,
            name=participant_name,
            expires_at=int(self._get_meeting_expiration(booking.end_time)),
        )
        meeting_url = await self._generate_url(
            booking=booking,
            participant_video_token=participant_video_token,
            participant_chat_token=participant_chat_token,
            is_update_url_data=is_update_url_data,
            external_id_prefix=external_id_prefix,
        )
        if is_update_url_in_db:
            await self._ensure_metadata_sync(booking.uid)
            await self.db.update_booking_video_url(booking.uid, meeting_url)
        return meeting_url

    async def get_meeting_url(self, booking: BookingDTO, external_id_prefix: str = "") -> str | None:
        return await self.shortener.get_url(external_id=f"{external_id_prefix}{booking.uid}")

    async def delete_meeting_url(
        self,
        *,
        booking: BookingDTO,
        external_id_prefix: str = "",
    ) -> None:
        await self.shortener.delete_url(external_id=f"{external_id_prefix}{booking.uid}")

    def _get_meeting_expiration(self, end_time: datetime) -> float:
        return end_time.timestamp() + self.timeshift

    def _create_jitsi_token(self, *, booking: BookingDTO, participant_name: str, external_id_prefix: str) -> str:
        payload = {
            "aud": self.settings.meeting_jwt_aud,
            "iss": self.settings.meeting_jwt_iss,
            "sub": "*",
            "room": booking.uid,
            "iat": int(time.time()),
            "nbf": booking.start_time.timestamp() - self.timeshift,
            "exp": self._get_meeting_expiration(booking.end_time),
            "context": {"user": {"name": participant_name, "role": "client" if external_id_prefix else "organizer"}},
        }
        return jwt.encode(payload, self.settings.jitsi_jwt_token, algorithm="HS256")

    async def _generate_url(
        self,
        *,
        booking: BookingDTO,
        participant_video_token: str,
        participant_chat_token: str,
        is_update_url_data: bool = False,
        external_id_prefix: str = "",
    ) -> str:
        long_url = (
            f"{self.settings.meeting_host_url}/{booking.uid}"
            f"?jwt_video={participant_video_token}&jwt_chat={participant_chat_token}"
        )
        try:
            expires_at = self._get_meeting_expiration(booking.end_time)
            if is_update_url_data:
                old_external_id = external_id_prefix + (booking.from_reschedule or booking.uid)
                short_url = await self.shortener.update_url_data(
                    long_url=long_url,
                    expires_at=expires_at,
                    new_external_id=external_id_prefix + booking.uid,
                    old_external_id=old_external_id,
                )
            else:
                short_url = await self.shortener.create_url(
                    long_url=long_url,
                    expires_at=expires_at,
                    external_id=external_id_prefix + booking.uid,
                )

            final_url = short_url if short_url else long_url
        except Exception:
            logger.exception("Error generating URL")
            final_url = long_url
        return final_url

    async def _ensure_metadata_sync(self, uid: str) -> None:
        for _ in range(METADATA_WAIT_ATTEMPTS):
            await sleep(METADATA_WAIT_DELAY)
            booking = await self.db.get_booking(uid)
            if booking and booking.metadata and str(booking.metadata) != "{}":
                return
