import json

import jwt
import structlog
from redis.asyncio import Redis

from app.adapters.db import BookingDatabaseAdapter
from app.controllers.notification import NotificationController
from app.dtos import MeetWebhookEventDTO, MeetWebhookEventType, TriggerEvent


logger = structlog.get_logger(__name__)


class MeetWebhookController:
    def __init__(
        self,
        db: BookingDatabaseAdapter,
        notification_controller: NotificationController,
        redis: Redis,
    ) -> None:
        self.db = db
        self.notification_controller = notification_controller
        self.redis = redis

    async def handle_webhook(self, event: MeetWebhookEventDTO) -> None:
        claims = jwt.decode(event.jwt.encode(), options={"verify_signature": False})
        role = claims.get("context", {}).get("user", {}).get("role")
        room = claims["room"]
        if event.event == MeetWebhookEventType.VIDEO_CONFERENCE_JOINED and role == "client":
            redis_key = f"meet_notified:{room}"
            if await self.redis.get(redis_key):
                logger.info(f"Notification already sent for room {room}")
                return None

            booking = await self.db.get_booking(room)
            if not booking:
                return None

            await self.notification_controller.notify_organizer_telegram(
                booking=booking,
                trigger_event=TriggerEvent.MEET_CLIENT_JOINED,
                user=booking.user,
                meeting_url=json.loads(booking.metadata).get("videoCallUrl"),
            )
            await self.redis.set(redis_key, 1, ex=60 * 60 * 2)
        return None
