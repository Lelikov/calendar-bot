import structlog

from app.clients.postal_client import EmailAddress, PostalClient, PostalError, SendMessageRequest
from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()


class EmailService:
    def __init__(self, from_email: str, from_email_name: str) -> None:
        self.from_email = from_email
        self.from_email_name = from_email_name

    async def send_email(self, to_email: str, subject: str, html_content: str) -> None:
        async with PostalClient(
            api_url=cfg.email_api_url,
            api_key=cfg.email_api_key,
            max_retries=3,
        ) as client:
            request_advanced = SendMessageRequest(
                to=[
                    EmailAddress(email=to_email),
                ],
                from_address=EmailAddress(email=self.from_email, name=self.from_email_name),
                subject=subject,
                html_body=html_content,
            )

            try:
                response = await client.send_message(request_advanced)
                logger.info(
                    "Email sent successfully",
                    to_email=to_email,
                    subject=subject,
                    email_message_id=response.message_id,
                )
            except PostalError as e:
                logger.exception("Failed to send email", to_email=to_email, error=str(e))
                raise
