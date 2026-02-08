import json

import jwt
import structlog

from app.dtos import MeetWebhookEventDTO, MeetWebhookEventType, TriggerEvent
from app.interfaces.booking import IBookingDatabaseAdapter
from app.interfaces.meeting import IMeetNotificationStateController
from app.interfaces.notification import INotificationController


logger = structlog.get_logger(__name__)


class MeetWebhookController:
    def __init__(
        self,
        db: IBookingDatabaseAdapter,
        notification_controller: INotificationController,
        meet_notification_state_controller: IMeetNotificationStateController,
    ) -> None:
        self.db = db
        self.notification_controller = notification_controller
        self.meet_notification_state_controller = meet_notification_state_controller

    async def handle_webhook(self, event: MeetWebhookEventDTO) -> None:
        claims = jwt.decode(event.jwt.encode(), options={"verify_signature": False})
        role = claims.get("context", {}).get("user", {}).get("role")
        room = claims["room"]
        if event.event == MeetWebhookEventType.VIDEO_CONFERENCE_JOINED and role == "client":
            if await self.meet_notification_state_controller.was_notified(room):
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
            await self.meet_notification_state_controller.mark_notified(room=room, ttl_seconds=60 * 60 * 2)
        return None
