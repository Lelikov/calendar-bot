import json

import jwt
import structlog

from app.dtos import MeetWebhookEventDTO, MeetWebhookEventType, TriggerEvent
from app.interfaces.booking import IBookingDatabaseAdapter
from app.interfaces.meeting import INotificationStateController
from app.interfaces.notification import INotificationController


logger = structlog.get_logger(__name__)

CLIENT_ENTER_NOTIFICATION_KEY = "client_enter_notified"
BOOKING_REMINDER_TTL_SECONDS = 60 * 60 * 2


class MeetWebhookController:
    def __init__(
        self,
        db: IBookingDatabaseAdapter,
        notification_controller: INotificationController,
        notification_state_controller: INotificationStateController,
    ) -> None:
        self.db = db
        self.notification_controller = notification_controller
        self.notification_state_controller = notification_state_controller

    async def handle_webhook(self, event: MeetWebhookEventDTO) -> None:
        claims = jwt.decode(event.jwt.encode(), options={"verify_signature": False})
        role = claims.get("context", {}).get("user", {}).get("role")
        room = claims["room"]
        if event.event == MeetWebhookEventType.VIDEO_CONFERENCE_JOINED and role == "client":
            if await self.notification_state_controller.was_notified(room=room, key=CLIENT_ENTER_NOTIFICATION_KEY):
                logger.info(f"Notification already sent for room {room}")
                return None

            booking = await self.db.get_booking(room)
            if not booking:
                return None

            metadata = json.loads(booking.metadata) if isinstance(booking.metadata, str) else booking.metadata

            await self.notification_controller.notify_organizer_telegram(
                booking=booking,
                trigger_event=TriggerEvent.MEET_CLIENT_JOINED,
                user=booking.user,
                meeting_url=metadata.get("videoCallUrl"),
            )
            await self.notification_state_controller.mark_notified(
                room=room,
                key=CLIENT_ENTER_NOTIFICATION_KEY,
                ttl_seconds=BOOKING_REMINDER_TTL_SECONDS,
            )
        return None
