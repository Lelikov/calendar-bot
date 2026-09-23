from app.dtos import EmailEventDTO
from app.interfaces.mail import IEmailEventDatabaseAdapter
from app.interfaces.sql import ISqlExecutor


class EmailEventDatabaseAdapter(IEmailEventDatabaseAdapter):
    """Storage for email delivery statuses.

    Kept apart from BookingDatabaseAdapter: that one reads Cal.com's tables, while
    email_event belongs to this service (see migrations/001_email_event.sql).
    """

    def __init__(self, sql: ISqlExecutor) -> None:
        self.sql = sql

    async def save_event(self, event: EmailEventDTO) -> bool:
        """Store one delivery status. Returns False if the event was already stored.

        Unisender repeats a webhook call until it is answered with 200, so the same
        event arrives more than once; the unique index decides which insert wins.
        """
        query = """
                INSERT INTO email_event (booking_uid, trigger_event, role, job_id, email,
                                         status, event_time, delivery_status, destination_response)
                VALUES (:booking_uid, :trigger_event, :role, :job_id, :email,
                        :status, :event_time, :delivery_status, :destination_response)
                ON CONFLICT DO NOTHING
                RETURNING id
                """
        row = await self.sql.execute_returning(
            query,
            {
                "booking_uid": event.booking_uid,
                "trigger_event": event.trigger_event,
                "role": event.role,
                "job_id": event.job_id,
                "email": event.email,
                "status": event.status,
                "event_time": event.event_time,
                "delivery_status": event.delivery_status,
                "destination_response": event.destination_response,
            },
        )
        return row is not None
