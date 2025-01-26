from redis.asyncio.connection import ConnectionPool

from app.settings import get_settings


cfg = get_settings()

pool = ConnectionPool.from_url(cfg.redis_url)
