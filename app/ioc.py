from aiogram import Bot
from dishka import Provider, Scope, provide

from app.bot import bot as telegram_bot
from app.controllers.mail import MailController
from app.settings import Settings, get_settings


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def provide_settings(self) -> Settings:
        return get_settings()

    @provide(scope=Scope.APP)
    def provide_bot(self) -> Bot:
        return telegram_bot

    @provide(scope=Scope.APP)
    def provide_mail_controller(self, bot: Bot, settings: Settings) -> MailController:
        return MailController(bot=bot, settings=settings)
