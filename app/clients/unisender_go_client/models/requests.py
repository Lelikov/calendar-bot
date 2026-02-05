from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from app.clients.models import Attachment, EmailAddress


class SendMessageRequest(BaseModel):
    to: list[str | EmailAddress] = Field(..., min_length=1)
    from_address: str | EmailAddress
    subject: str
    reply_address: str | EmailAddress | None = None
    plain_body: str | None = None
    html_body: str | None = None
    attachments: list[Attachment] | None = None
    headers: dict[str, str] | None = None
    track_links: int | None = 0
    track_read: int | None = 0

    @model_validator(mode="after")
    def validate_body(self) -> Self:
        if self.plain_body is None and self.html_body is None:
            raise ValueError("At least one of plain_body or html_body must be provided")
        return self

    def model_dump(self, **_: Any) -> dict[str, Any]:  # noqa: C901
        message: dict[str, Any] = {}

        # Recipients
        recipients = []
        for recipient in self.to:
            if isinstance(recipient, EmailAddress):
                recipients.append({"email": recipient.email})
            else:
                recipients.append({"email": recipient})
        message["recipients"] = recipients

        # Body
        body = {}
        if self.html_body:
            body["html"] = self.html_body
        if self.plain_body:
            body["plaintext"] = self.plain_body
        message["body"] = body

        message["subject"] = self.subject

        # From
        if isinstance(self.from_address, EmailAddress):
            message["from_email"] = self.from_address.email
            if self.from_address.name:
                message["from_name"] = self.from_address.name
        else:
            message["from_email"] = self.from_address

        if isinstance(self.reply_address, EmailAddress):
            message["reply_to"] = self.reply_address.email
            if self.from_address.name:
                message["reply_to_name"] = self.reply_address.name
        else:
            message["reply_to"] = self.reply_address

        # Attachments
        if self.attachments:
            message["attachments"] = [
                {"type": att.content_type, "name": att.name, "content": att.data} for att in self.attachments
            ]

        if self.headers:
            message["headers"] = self.headers

        if self.track_links is not None:
            message["track_links"] = self.track_links
        if self.track_read is not None:
            message["track_read"] = self.track_read

        return {"message": message}
