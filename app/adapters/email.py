from typing import Protocol

import structlog

from app.clients.models import EmailAddress
from app.clients.unisender_go_client import SendMessageRequest as UnisenderSendMessageRequest
from app.clients.unisender_go_client import UnisenderGoClient, UnisenderGoError


logger = structlog.get_logger(__name__)


class IEmailClient(Protocol):
    async def send_email(
        self,
        to_email: str,
        from_email: str,
        from_email_name: str | None,
        reply_to_email: str | None,
        reply_to_email_name: str | None,
        subject: str,
        html_content: str,
    ) -> None: ...


class UnisenderGoEmailClient(IEmailClient):
    def __init__(self, api_url: str, api_key: str, max_retries: int = 3) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.max_retries = max_retries

    async def send_email(
        self,
        to_email: str,
        from_email: str,
        from_email_name: str | None,
        reply_to_email: str | None,
        reply_to_email_name: str | None,
        subject: str,
        html_content: str,
    ) -> None:
        async with UnisenderGoClient(
            api_url=self.api_url,
            api_key=self.api_key,
            max_retries=self.max_retries,
        ) as client:
            request = UnisenderSendMessageRequest(
                to=[EmailAddress(email=to_email)],
                from_address=EmailAddress(email=from_email, name=from_email_name),
                reply_address=EmailAddress(email=reply_to_email, name=reply_to_email_name) if reply_to_email else None,
                subject=subject,
                html_body=html_content,
            )

            try:
                response = await client.send_message(request)
                logger.info(
                    "Email sent successfully via Unisender Go",
                    to_email=to_email,
                    subject=subject,
                    email_message_id=response.message_id,
                )
            except UnisenderGoError as e:
                logger.exception("Failed to send email via Unisender Go", to_email=to_email, error=str(e))
                raise
