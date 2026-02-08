from typing import Any

from redis.asyncio import Redis

from app.interfaces.cache import ICacheController


class CacheController(ICacheController):
    def __init__(self, client: Redis) -> None:
        self.client = client

    async def get(self, key: str) -> Any | None:
        return await self.client.get(key)

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        await self.client.set(key, value, ex=ttl_seconds)
