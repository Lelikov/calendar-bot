from typing import Any, Self

from pydantic import BaseModel, Field, model_validator

from .common import Attachment, EmailAddress


class SendMessageRequest(BaseModel):
    to: list[str | EmailAddress] = Field(..., min_length=1)
    from_address: str | EmailAddress
    subject: str
    plain_body: str | None = None
    html_body: str | None = None
    cc: list[str | EmailAddress] | None = None
    bcc: list[str | EmailAddress] | None = None
    reply_to: str | None = None
    attachments: list[Attachment] | None = None
    headers: dict[str, str] | None = None
    bounce: bool | None = None
    tag: str | None = None

    @model_validator(mode="after")
    def validate_body(self) -> Self:
        if self.plain_body is None and self.html_body is None:
            raise ValueError("At least one of plain_body or html_body must be provided")
        return self

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(**kwargs)

        def convert(v: str | EmailAddress) -> str:
            return v.to_string() if isinstance(v, EmailAddress) else v

        for field in ["to", "cc", "bcc"]:
            if field in data:
                val = getattr(self, field)
                if val:
                    data[field] = [convert(x) for x in val]

        data["from"] = convert(self.from_address)
        del data["from_address"]

        return data
