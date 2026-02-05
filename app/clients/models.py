from pydantic import BaseModel, EmailStr


class Attachment(BaseModel):
    name: str
    content_type: str
    data: str


class EmailAddress(BaseModel):
    email: EmailStr
    name: str | None = None

    def to_string(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email
