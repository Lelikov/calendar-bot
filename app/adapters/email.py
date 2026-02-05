from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol

import aiosmtplib
import structlog

from app.clients.postal_client import EmailAddress, PostalClient, PostalError
from app.clients.postal_client import SendMessageRequest as PostalSendMessageRequest
from app.clients.unisender_go_client import (
    SendMessageRequest as UnisenderSendMessageRequest,
)
from app.clients.unisender_go_client import (
    UnisenderGoClient,
    UnisenderGoError,
)
from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()


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


class PostalEmailClient:
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
        async with PostalClient(
            api_url=self.api_url,
            api_key=self.api_key,
            max_retries=self.max_retries,
        ) as client:
            request = PostalSendMessageRequest(
                to=[EmailAddress(email=to_email)],
                from_address=EmailAddress(email=from_email, name=from_email_name),
                reply_address=EmailAddress(email=reply_to_email, name=reply_to_email_name) if reply_to_email else None,
                subject=subject,
                html_body=html_content,
            )

            try:
                response = await client.send_message(request)
                logger.info(
                    "Email sent successfully via Postal",
                    to_email=to_email,
                    subject=subject,
                    email_message_id=response.message_id,
                )
            except PostalError as e:
                logger.exception("Failed to send email via Postal", to_email=to_email, error=str(e))
                raise


class SMTPClient:
    """SMTP client using aiosmtplib to implement EmailClient interface."""

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    async def send_email(
        self,
        to_email: str,
        from_email: str,
        from_email_name: str | None,
        subject: str,
        html_content: str,
    ) -> None:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"{from_email_name} <{from_email}>" if from_email_name else from_email
        message["To"] = to_email

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        try:
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                start_tls=True,
            )
            logger.info(
                "Email sent successfully via SMTP",
                to_email=to_email,
                subject=subject,
                smtp_host=self.host,
            )
        except Exception as e:
            logger.exception("Failed to send email via SMTP", to_email=to_email, error=str(e))
            raise


class EmailService:
    def __init__(
        self,
        from_email: str,
        from_email_name: str,
        reply_to_email: str,
        reply_to_email_name: str,
    ) -> None:
        self.from_email = from_email
        self.from_email_name = from_email_name
        self.reply_to_email = reply_to_email
        self.reply_to_email_name = reply_to_email_name

        self.email_client_selector: dict[str, type[IEmailClient]] = {
            "default": UnisenderGoEmailClient,
        }

    def get_client_by_email(self, to_email: str) -> IEmailClient:
        domain = to_email.split("@")[-1]

        client_class = self.email_client_selector.get(domain, self.email_client_selector["default"])

        if client_class == SMTPClient:
            if not all([cfg.smtp_host, cfg.smtp_port, cfg.smtp_user, cfg.smtp_password]):
                logger.warning(
                    f"SMTP credentials not configured, falling back to {client_class.__name__}",
                    domain=domain,
                    to_email=to_email,
                )
                return client_class(
                    api_url=cfg.email_api_url,
                    api_key=cfg.email_api_key,
                    max_retries=3,
                )

            logger.debug("Using SMTP client", domain=domain, to_email=to_email)
            return SMTPClient(
                host=cfg.smtp_host,
                port=cfg.smtp_port,
                username=cfg.smtp_user,
                password=cfg.smtp_password,
            )

        logger.debug(f"Using {client_class.__name__} client", domain=domain, to_email=to_email)
        return client_class(
            api_url=cfg.email_api_url,
            api_key=cfg.email_api_key,
            max_retries=3,
        )

    async def send_email(self, to_email: str, subject: str, html_content: str) -> None:
        client = self.get_client_by_email(to_email=to_email)
        await client.send_email(
            to_email=to_email,
            from_email=self.from_email,
            from_email_name=self.from_email_name,
            reply_to_email=self.reply_to_email,
            reply_to_email_name=self.reply_to_email_name,
            subject=subject,
            html_content=html_content,
        )
