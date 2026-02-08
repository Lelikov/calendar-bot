from app.interfaces.cache import ICacheController
from app.interfaces.meeting import INotificationStateController


class NotificationStateController(INotificationStateController):
    def __init__(self, cache_controller: ICacheController) -> None:
        self.cache_controller = cache_controller

    @staticmethod
    def _build_key(room: str, key: str) -> str:
        return f"{key}:{room}"

    async def was_notified(self, room: str, key: str) -> bool:
        return bool(await self.cache_controller.get(self._build_key(room, key=key)))

    async def mark_notified(self, room: str, ttl_seconds: int, key: str) -> None:
        await self.cache_controller.set(self._build_key(room, key=key), 1, ttl_seconds=ttl_seconds)
