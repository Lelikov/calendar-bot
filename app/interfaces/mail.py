from __future__ import annotations
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from app.dtos import MailWebhookEventDTO


class IEmailClient(Protocol):
    async def send_email(
        self,
        to_email: str,
        from_email: str | None = None,
        from_email_name: str | None = None,
        reply_to_email: str | None = None,
        reply_to_email_name: str | None = None,
        subject: str | None = None,
        html_content: str | None = None,
        context: dict | None = None,
        template_id: str | None = None,
    ) -> None: ...


class IEmailController(Protocol):
    async def send_email(
        self,
        to_email: str,
        subject: str | None = None,
        context: dict | None = None,
        template_id: str | None = None,
    ) -> None: ...


class IMailWebhookController(Protocol):
    async def handle_webhook(self, event: MailWebhookEventDTO) -> None: ...
