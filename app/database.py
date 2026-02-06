from databases import Database

from app.settings import get_settings


cfg = get_settings()
database = Database(cfg.postgres_dsn)
