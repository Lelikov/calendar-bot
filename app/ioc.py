from collections.abc import AsyncGenerator
from typing import Any

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dishka import Provider, Scope, provide
from redis.asyncio import ConnectionPool, Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.email import UnisenderGoEmailClient
from app.adapters.get_stream import GetStreamAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.adapters.sql import SqlExecutor
from app.controllers.booking import BookingController
from app.controllers.chat import ChatController
from app.controllers.email import EmailController
from app.controllers.mail_webhook import MailWebhookController
from app.controllers.meet_webhook import MeetWebhookController
from app.controllers.meeting import MeetingController
from app.controllers.notification import NotificationController
from app.controllers.telegram import TelegramController
from app.interfaces.booking import IBookingController, IBookingDatabaseAdapter
from app.interfaces.chat import IChatClient, IChatController
from app.interfaces.mail import IEmailClient, IEmailController, IMailWebhookController
from app.interfaces.meeting import IMeetingController, IMeetWebhookController
from app.interfaces.notification import INotificationController
from app.interfaces.sql import ISqlExecutor
from app.interfaces.telegram import ITelegramController
from app.interfaces.url_shortener import IUrlShortener
from app.settings import Settings


dp = Dispatcher()
telegram_router = Router(name="telegram")
dp.include_router(telegram_router)


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def provide_settings(self) -> Settings:
        return Settings()

    @provide(scope=Scope.APP)
    def provide_bot(self, settings: Settings) -> Bot:
        return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    @provide(scope=Scope.APP)
    def provide_db_engine(self, settings: Settings) -> AsyncEngine:
        return create_async_engine(
            settings.postgres_dsn,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )

    @provide(scope=Scope.APP)
    def provide_sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @provide(scope=Scope.REQUEST)
    async def provide_session(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> AsyncGenerator[AsyncSession, Any]:
        async with sessionmaker() as session:
            yield session

    @provide(scope=Scope.REQUEST)
    def provide_sql_executor(self, session: AsyncSession) -> ISqlExecutor:
        return SqlExecutor(session)

    @provide(scope=Scope.APP)
    def provide_redis(self, settings: Settings) -> Redis:
        return Redis(connection_pool=ConnectionPool.from_url(settings.redis_url))

    @provide(scope=Scope.APP)
    def provide_mail_webhook_controller(self, bot: Bot, settings: Settings) -> IMailWebhookController:
        return MailWebhookController(bot=bot, settings=settings)

    @provide(scope=Scope.APP)
    def provide_email_client(self, settings: Settings) -> IEmailClient:
        return UnisenderGoEmailClient(
            api_url=settings.email_api_url,
            api_key=settings.email_api_key,
            max_retries=3,
        )

    @provide(scope=Scope.APP)
    def provide_email_controller(self, client: IEmailClient, settings: Settings) -> IEmailController:
        return EmailController(client=client, settings=settings)

    @provide(scope=Scope.REQUEST)
    def provide_db(self, sql: ISqlExecutor) -> IBookingDatabaseAdapter:
        return BookingDatabaseAdapter(sql)

    @provide(scope=Scope.APP)
    def provide_shortener(self, settings: Settings) -> IUrlShortener:
        return UrlShortenerAdapter(settings=settings)

    @provide(scope=Scope.APP)
    def provide_chat_adapter(self, settings: Settings) -> IChatClient:
        return GetStreamAdapter(
            chat_api_key=settings.chat_api_key,
            chat_api_secret=settings.chat_api_secret,
            user_id_encryption_key=settings.chat_user_id_encryption_key,
        )

    @provide(scope=Scope.APP)
    def provide_chat_controller(self, chat_adapter: IChatClient) -> IChatController:
        return ChatController(client=chat_adapter)

    @provide(scope=Scope.REQUEST)
    def provide_meeting_controller(
        self,
        db: IBookingDatabaseAdapter,
        shortener: IUrlShortener,
        chat_controller: IChatController,
        settings: Settings,
    ) -> IMeetingController:
        return MeetingController(db=db, shortener=shortener, chat_controller=chat_controller, settings=settings)

    @provide(scope=Scope.REQUEST)
    def provide_notification_controller(
        self,
        db: IBookingDatabaseAdapter,
        bot: Bot,
        settings: Settings,
        email_controller: IEmailController,
    ) -> INotificationController:
        return NotificationController(db=db, bot=bot, settings=settings, email_controller=email_controller)

    @provide(scope=Scope.APP)
    def provide_telegram_controller(self, bot: Bot, settings: Settings) -> ITelegramController:
        return TelegramController(bot=bot, settings=settings)

    @provide(scope=Scope.REQUEST)
    def provide_meet_webhook_controller(
        self,
        db: IBookingDatabaseAdapter,
        notification_controller: INotificationController,
        redis: Redis,
    ) -> IMeetWebhookController:
        return MeetWebhookController(db=db, notification_controller=notification_controller, redis=redis)

    @provide(scope=Scope.REQUEST)
    def provide_booking_controller(
        self,
        db: IBookingDatabaseAdapter,
        shortener: IUrlShortener,
        chat_controller: IChatController,
        meeting_controller: IMeetingController,
        notification_controller: INotificationController,
    ) -> IBookingController:
        return BookingController(
            db=db,
            shortener=shortener,
            chat_controller=chat_controller,
            meeting_controller=meeting_controller,
            notification_controller=notification_controller,
        )
