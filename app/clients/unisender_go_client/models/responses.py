from pydantic import BaseModel


class SendMessageResponse(BaseModel):
    status: str
    job_id: str | None = None
    emails: list[str] | None = None
    tags: list[str] | None = None
    code: str | int | None = None
    message: str | None = None

    @property
    def is_success(self) -> bool:
        return self.status == "success"
