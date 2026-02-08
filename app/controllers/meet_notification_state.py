from app.interfaces.cache import ICacheController
from app.interfaces.meeting import IMeetNotificationStateController


class MeetNotificationStateController(IMeetNotificationStateController):
    def __init__(self, cache_controller: ICacheController) -> None:
        self.cache_controller = cache_controller

    @staticmethod
    def _build_key(room: str) -> str:
        return f"meet_notified:{room}"

    async def was_notified(self, room: str) -> bool:
        return bool(await self.cache_controller.get(self._build_key(room)))

    async def mark_notified(self, room: str, ttl_seconds: int) -> None:
        await self.cache_controller.set(self._build_key(room), 1, ttl_seconds=ttl_seconds)
