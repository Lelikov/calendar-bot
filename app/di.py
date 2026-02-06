from dishka import make_async_container
from dishka.integrations.aiogram import AiogramProvider
from dishka.integrations.fastapi import FastapiProvider

from app.ioc import AppProvider


container = make_async_container(AppProvider(), FastapiProvider(), AiogramProvider())
