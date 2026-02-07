from __future__ import annotations
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from app.dtos import MailWebhookEventDTO


class IEmailClient(Protocol):
    async def send_email(
        self,
        to_email: str,
        from_email: str,
        from_email_name: str,
        reply_to_email: str,
        reply_to_email_name: str,
        subject: str,
        html_content: str,
    ) -> None: ...


class IEmailController(Protocol):
    async def send_email(self, to_email: str, subject: str, html_content: str) -> None: ...


class IMailWebhookController(Protocol):
    async def handle_webhook(self, event: MailWebhookEventDTO) -> None: ...
