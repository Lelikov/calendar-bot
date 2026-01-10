from typing import Any

from pydantic import BaseModel


class MessageStatus(BaseModel):
    id: int
    token: str


class SendMessageData(BaseModel):
    message_id: str
    messages: dict[str, MessageStatus]


class SendMessageResponse(BaseModel):
    status: str
    time: float
    flags: dict[str, Any]
    data: SendMessageData | dict[str, Any]

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def message_id(self) -> str | None:
        if isinstance(self.data, SendMessageData):
            return self.data.message_id
        return None
