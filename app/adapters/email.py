import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import structlog


logger = structlog.get_logger(__name__)


class EmailService:
    def __init__(self, host: str, port: int, from_email: str) -> None:
        self.host = host
        self.port = port
        self.from_email = from_email

    def send_email(self, to_email: str, subject: str, html_content: str) -> None:
        msg = MIMEMultipart()
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.send_message(msg)
            logger.info("Email sent successfully", to_email=to_email, subject=subject)
        except Exception as e:
            logger.exception("Failed to send email", to_email=to_email, error=str(e))
            raise
