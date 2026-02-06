from aiogram import Dispatcher, Router
from dishka.integrations.aiogram import setup_dishka

from app.di import container


dp = Dispatcher()
telegram_router = Router(name="telegram")
dp.include_router(telegram_router)

setup_dishka(container=container, router=dp, auto_inject=True)
