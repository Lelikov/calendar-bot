from databases import Database

from app.settings import Settings


def create_database(settings: Settings) -> Database:
    return Database(settings.postgres_dsn)
