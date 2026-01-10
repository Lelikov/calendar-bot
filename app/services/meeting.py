import time
from asyncio import sleep

import jwt
import structlog
from dateutil import parser

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.dtos import BookingEventPayloadDTO
from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()

METADATA_WAIT_ATTEMPTS = 1
METADATA_WAIT_DELAY = 5


class MeetingService:
    def __init__(self, db: BookingDatabaseAdapter, shortener: UrlShortenerAdapter) -> None:
        self.db = db
        self.shortener = shortener
        self.timeshift = 5 * 60

    async def setup_meeting(
        self,
        *,
        booking_event_payload: BookingEventPayloadDTO,
        participant_name: str,
        is_update_url_data: bool = False,
        is_update_url_in_db: bool = False,
        external_id_prefix: str = "",
    ) -> str:
        meeting_url = await self._generate_url(
            booking_event_payload=booking_event_payload,
            participant_token=self._create_jitsi_token(
                booking_event_payload=booking_event_payload,
                participant_name=participant_name,
            ),
            is_update_url_data=is_update_url_data,
            external_id_prefix=external_id_prefix,
        )
        if is_update_url_in_db:
            await self._ensure_metadata_sync(booking_event_payload.uid)
            await self.db.update_booking_video_url(booking_event_payload.uid, meeting_url)
        return meeting_url

    async def delete_meeting(
        self,
        *,
        booking_event_payload: BookingEventPayloadDTO,
        external_id_prefix: str = "",
    ) -> None:
        await self.shortener.delete_url(external_id=f"{external_id_prefix}{booking_event_payload.uid}")

    def _get_meeting_expiration(self, end_time: str) -> float:
        return parser.parse(end_time).timestamp() + self.timeshift

    def _create_jitsi_token(self, *, booking_event_payload: BookingEventPayloadDTO, participant_name: str) -> str:
        payload = {
            "aud": cfg.meeting_jwt_aud,
            "iss": cfg.meeting_jwt_iss,
            "sub": "*",
            "room": booking_event_payload.uid,
            "iat": int(time.time()),
            "nbf": parser.parse(booking_event_payload.start_time).timestamp() - self.timeshift,
            "exp": self._get_meeting_expiration(booking_event_payload.end_time),
            "context": {"user": {"name": participant_name}},
        }
        return jwt.encode(payload, cfg.jitsi_jwt_token, algorithm="HS256")

    async def _generate_url(
        self,
        *,
        booking_event_payload: BookingEventPayloadDTO,
        participant_token: str,
        is_update_url_data: bool = False,
        external_id_prefix: str = "",
    ) -> str:
        long_url = f"{cfg.meeting_host_url}/{booking_event_payload.uid}?jwt={participant_token}"
        try:
            expires_at = self._get_meeting_expiration(booking_event_payload.end_time)
            if is_update_url_data:
                old_external_id = external_id_prefix + (
                    booking_event_payload.reschedule_uid or booking_event_payload.uid
                )
                short_url = await self.shortener.update_url_data(
                    long_url=long_url,
                    expires_at=expires_at,
                    new_external_id=external_id_prefix + booking_event_payload.uid,
                    old_external_id=old_external_id,
                )
            else:
                short_url = await self.shortener.create_url(
                    long_url=long_url,
                    expires_at=expires_at,
                    external_id=external_id_prefix + booking_event_payload.uid,
                )

            final_url = short_url if short_url else long_url
        except Exception:
            logger.exception("Error generating URL")
            final_url = long_url
        return final_url

    async def _ensure_metadata_sync(self, uid: str) -> None:
        for _ in range(METADATA_WAIT_ATTEMPTS):
            await sleep(METADATA_WAIT_DELAY)
            metadata = await self.db.get_booking_metadata(uid)
            if metadata and str(metadata) != "{}":
                return
