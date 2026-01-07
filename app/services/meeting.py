import time
from asyncio import sleep

import jwt
import structlog
from dateutil import parser

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.schemas import BookingEventPayload
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

    def _create_jitsi_token(self, booking_event_payload: BookingEventPayload, name: str) -> str:
        payload = {
            "aud": "jitsi.zhivaya",
            "iss": "jitsi.zhivaya",
            "sub": "*",
            "room": booking_event_payload.uid,
            "iat": int(time.time()),
            "nbf": parser.parse(booking_event_payload.start_time).timestamp() - self.timeshift,
            "exp": parser.parse(booking_event_payload.end_time).timestamp() + self.timeshift,
            "context": {"user": {"name": name}},
        }
        return jwt.encode(payload, cfg.jitsi_jwt_token, algorithm="HS256")

    async def _generate_url(
        self,
        booking_event_payload: BookingEventPayload,
        organizer_token: str,
        is_update: bool = False,
    ) -> str:
        long_url = f"https://meet.zhivaya.org/{booking_event_payload.uid}?jwt={organizer_token}"
        try:
            expires_at = parser.parse(booking_event_payload.end_time).timestamp() + self.timeshift
            if is_update:
                short_url = await self.shortener.update_short_url(
                    long_url=long_url,
                    expires_at=expires_at,
                    new_external_id=booking_event_payload.uid,
                    old_external_id=booking_event_payload.reschedule_uid or booking_event_payload.uid,
                )
            else:
                short_url = await self.shortener.create_short_url(
                    long_url=long_url,
                    expires_at=expires_at,
                    external_id=booking_event_payload.uid,
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

    async def setup_meeting(
        self,
        booking_event_payload: BookingEventPayload,
        organizer_name: str,
        is_update: bool = False,
    ) -> str:
        organizer_token = self._create_jitsi_token(booking_event_payload, organizer_name)
        meeting_url = await self._generate_url(booking_event_payload, organizer_token, is_update)

        await self._ensure_metadata_sync(booking_event_payload.uid)
        await self.db.update_booking_video_url(booking_event_payload.uid, meeting_url)
        return meeting_url
