from redis.asyncio.connection import ConnectionPool

from app.settings import Settings


def create_redis_pool(settings: Settings) -> ConnectionPool:
    return ConnectionPool.from_url(settings.redis_url)
