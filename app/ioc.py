from aiogram import Bot
from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from app.adapters.db import BookingDatabaseAdapter
from app.bot import bot as telegram_bot
from app.controllers.mail import MailController
from app.controllers.meet import MeetController
from app.redis_pool import pool
from app.services.notification import NotificationService
from app.settings import Settings, get_settings


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def provide_settings(self) -> Settings:
        return get_settings()

    @provide(scope=Scope.APP)
    def provide_bot(self) -> Bot:
        return telegram_bot

    @provide(scope=Scope.APP)
    def provide_db(self, settings: Settings) -> BookingDatabaseAdapter:
        return BookingDatabaseAdapter(settings.postgres_dsn)

    @provide(scope=Scope.APP)
    def provide_notification_service(self, db: BookingDatabaseAdapter, bot: Bot) -> NotificationService:
        return NotificationService(db=db, bot=bot)

    @provide(scope=Scope.APP)
    def provide_redis(self) -> Redis:
        return Redis(connection_pool=pool)

    @provide(scope=Scope.APP)
    def provide_mail_controller(self, bot: Bot, settings: Settings) -> MailController:
        return MailController(bot=bot, settings=settings)

    @provide(scope=Scope.APP)
    def provide_meet_controller(
        self,
        db: BookingDatabaseAdapter,
        notification_service: NotificationService,
        redis: Redis,
    ) -> MeetController:
        return MeetController(db=db, notification_service=notification_service, redis=redis)
