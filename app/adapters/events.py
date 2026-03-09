from typing import Any

import httpx
import structlog
from cloudevents.http import CloudEvent, to_binary
from fastapi.encoders import jsonable_encoder

from app.interfaces.events import EventType, IEventsAdapter


logger = structlog.get_logger(__name__)


class CloudEventsAdapter(IEventsAdapter):
    def __init__(
        self,
        *,
        endpoint_url: str | None,
        token: str | None,
        source: str,
        timeout_seconds: float,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.token = token
        self.source = source
        self.timeout_seconds = timeout_seconds

    async def send_event(self, booking_uid: str, event: EventType, data: dict[str, Any] | None = None) -> None:
        if not self.endpoint_url:
            logger.debug("Events endpoint is not configured, skipping event send", event=event)
            return

        if not data:
            data = {}

        encoded_data = jsonable_encoder({**data, "booking_uid": booking_uid})
        cloud_event = CloudEvent(
            {
                "type": f"booking.events.v1.{event}.create",
                "source": self.source,
            },
            encoded_data,
        )
        headers, body = to_binary(cloud_event)
        if self.token:
            headers["Authorization"] = self.token

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                request_kwargs: dict[str, Any] = {"headers": headers}
                if isinstance(body, dict | list):
                    request_kwargs["json"] = body
                else:
                    request_kwargs["content"] = body

                response = await client.post(self.endpoint_url, **request_kwargs)
                response.raise_for_status()
            logger.info("CloudEvent sent")
        except Exception:
            logger.exception("Failed to send CloudEvent")
