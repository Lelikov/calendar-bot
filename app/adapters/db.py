from databases import Database


class BookingDatabaseAdapter:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def get_user(self, email: str) -> dict | None:
        async with Database(self.dsn) as database:
            return await database.fetch_one(query="SELECT * FROM users WHERE email = :email", values={"email": email})

    async def get_organizer_chat_id(self, email: str) -> int | None:
        async with Database(self.dsn) as database:
            query = (
                "SELECT telegram_chat_id FROM users "
                "WHERE locked = FALSE "
                "AND email = :email "
                "AND telegram_chat_id IS NOT NULL"
            )
            row = await database.fetch_one(query=query, values={"email": email})
        if row:
            return row["telegram_chat_id"]
        return None

    async def get_booking_metadata(self, booking_uid: str) -> dict | None:
        async with Database(self.dsn) as database:
            row = await database.fetch_one(
                query='SELECT metadata FROM public."Booking" WHERE uid = :booking_uid',
                values={"booking_uid": booking_uid},
            )
            if row and row["metadata"]:
                return row["metadata"]
        return None

    async def update_booking_video_url(self, booking_uid: str, url: str) -> None:
        async with Database(self.dsn) as database:
            query = """
                UPDATE public."Booking"
                SET metadata = COALESCE(metadata, '{}'::jsonb) ||
                               jsonb_build_object('videoCallUrl', CAST(:url AS text))
                WHERE uid = :booking_uid
                    """
            await database.execute(query=query, values={"booking_uid": booking_uid, "url": url})
