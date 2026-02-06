from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from databases import Database
from dishka import Provider, Scope, provide
from redis.asyncio import Redis

from app.adapters.db import BookingDatabaseAdapter
from app.adapters.email import IEmailClient, UnisenderGoEmailClient
from app.adapters.get_stream import GetStreamAdapter
from app.adapters.shortener import UrlShortenerAdapter
from app.controllers.booking import BookingController
from app.controllers.chat import ChatController
from app.controllers.mail import MailWebhookController
from app.controllers.meet import MeetWebhookController
from app.database import create_database
from app.redis_pool import create_redis_pool
from app.services.email import EmailService
from app.services.meeting import MeetingService
from app.services.notification import NotificationService
from app.services.telegram import TelegramService
from app.settings import Settings


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def provide_settings(self) -> Settings:
        return Settings()

    @provide(scope=Scope.APP)
    def provide_bot(self, settings: Settings) -> Bot:
        return Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    @provide(scope=Scope.APP)
    def provide_database(self, settings: Settings) -> Database:
        return create_database(settings)

    @provide(scope=Scope.APP)
    def provide_redis(self, settings: Settings) -> Redis:
        return Redis(connection_pool=create_redis_pool(settings))

    @provide(scope=Scope.APP)
    def provide_mail_webhook_controller(self, bot: Bot, settings: Settings) -> MailWebhookController:
        return MailWebhookController(bot=bot, settings=settings)

    @provide(scope=Scope.APP)
    def provide_email_client(self, settings: Settings) -> IEmailClient:
        return UnisenderGoEmailClient(
            api_url=settings.email_api_url,
            api_key=settings.email_api_key,
            max_retries=3,
        )

    @provide(scope=Scope.APP)
    def provide_email_service(self, client: IEmailClient, settings: Settings) -> EmailService:
        return EmailService(client=client, settings=settings)

    @provide(scope=Scope.APP)
    def provide_db(self, database: Database) -> BookingDatabaseAdapter:
        return BookingDatabaseAdapter(database)

    @provide(scope=Scope.APP)
    def provide_shortener(self, settings: Settings) -> UrlShortenerAdapter:
        return UrlShortenerAdapter(settings=settings)

    @provide(scope=Scope.APP)
    def provide_chat_adapter(self, settings: Settings) -> GetStreamAdapter:
        return GetStreamAdapter(
            chat_api_key=settings.chat_api_key,
            chat_api_secret=settings.chat_api_secret,
            user_id_encryption_key=settings.chat_user_id_encryption_key,
        )

    @provide(scope=Scope.APP)
    def provide_chat_controller(self, chat_adapter: GetStreamAdapter) -> ChatController:
        return ChatController(client=chat_adapter)

    @provide(scope=Scope.APP)
    def provide_meeting_service(
        self,
        db: BookingDatabaseAdapter,
        shortener: UrlShortenerAdapter,
        chat_controller: ChatController,
        settings: Settings,
    ) -> MeetingService:
        return MeetingService(db=db, shortener=shortener, chat_controller=chat_controller, settings=settings)

    @provide(scope=Scope.APP)
    def provide_notification_service(
        self,
        db: BookingDatabaseAdapter,
        bot: Bot,
        settings: Settings,
        email_service: EmailService,
    ) -> NotificationService:
        return NotificationService(db=db, bot=bot, settings=settings, email_service=email_service)

    @provide(scope=Scope.APP)
    def provide_telegram_service(self, bot: Bot, settings: Settings) -> TelegramService:
        return TelegramService(bot=bot, settings=settings)

    @provide(scope=Scope.APP)
    def provide_meet_webhook_controller(
        self,
        db: BookingDatabaseAdapter,
        notification_service: NotificationService,
        redis: Redis,
    ) -> MeetWebhookController:
        return MeetWebhookController(db=db, notification_service=notification_service, redis=redis)

    @provide(scope=Scope.REQUEST)
    def provide_booking_controller(
        self,
        db: BookingDatabaseAdapter,
        shortener: UrlShortenerAdapter,
        chat_controller: ChatController,
        meeting_service: MeetingService,
        notification_service: NotificationService,
    ) -> BookingController:
        return BookingController(
            db=db,
            shortener=shortener,
            chat_controller=chat_controller,
            meeting_service=meeting_service,
            notification_service=notification_service,
        )
