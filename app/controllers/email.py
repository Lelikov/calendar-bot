from app.dtos import BookingDTO, EmailSendResultDTO
from app.interfaces.mail import IEmailClient
from app.settings import Settings


class EmailController:
    def __init__(self, client: IEmailClient, settings: Settings) -> None:
        self.client = client
        self.from_email = settings.from_email
        self.from_email_name = settings.from_email_name
        self.reply_to_email = settings.reply_to_email
        self.reply_to_email_name = settings.reply_to_email_name

    async def send_email(
        self,
        booking: BookingDTO,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> EmailSendResultDTO:
        return await self.client.send_email(
            booking=booking,
            to_email=to_email,
            from_email=self.from_email,
            from_email_name=self.from_email_name,
            reply_to_email=self.reply_to_email,
            reply_to_email_name=self.reply_to_email_name,
            subject=subject,
            html_content=html_content,
        )
