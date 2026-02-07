# Project Context: calendar-bot

## Overview
Calendar-bot is a FastAPI + Aiogram application that integrates booking workflows with chat, meeting links,
email notifications, and webhooks. The app follows DI/IoC using Dishka, with interfaces split by domain.

## Key Entrypoints
- `app/main.py`: FastAPI app setup, Dishka container wiring, lifespan startup tasks.
- `app/ioc.py`: Dishka providers; binds interfaces to concrete implementations.
- `app/routes.py`: FastAPI routes (booking, mail, jitsi, telegram webhook).
- `app/handlers/messages.py`: Aiogram message handlers.

## Domain Interfaces (Protocol)
Interfaces are grouped in `app/interfaces/`:
- `booking.py`: `IBookingDatabaseAdapter`, `IBookingController`
- `chat.py`: `IChatClient`, `IChatController`
- `meeting.py`: `IMeetingController`, `IMeetWebhookController`
- `mail.py`: `IEmailClient`, `IEmailController`, `IMailWebhookController`
- `notification.py`: `INotificationController`
- `sql.py`: `ISqlExecutor`
- `url_shortener.py`: `IUrlShortener`
- `telegram.py`: `ITelegramController`

`app/interfaces/__init__.py` exports everything for convenience.

## Controllers
- `BookingController`: orchestrates booking events, chats, meeting URLs, notifications.
- `MeetingController`: generates meeting/jitsi URLs + shortener integration.
- `NotificationController`: sends emails and Telegram notifications.
- `MeetWebhookController`: processes meeting webhooks (client joined).
- `MailWebhookController`: processes mail provider webhooks.
- `EmailController`: wraps email client with settings.
- `ChatController`: wraps chat client.
- `TelegramController`: starts Telegram bot.

## Adapters
- `adapters/sql.py`: `SqlExecutor` for DB access (used by `BookingDatabaseAdapter`).
- `adapters/db.py`: booking DB adapter.
- `adapters/get_stream.py`: chat client implementation.
- `adapters/shortener.py`: URL shortener implementation.
- `adapters/email.py`: Unisender Go email client implementation.

## DI/IoC
Dishka container in `app/ioc.py` wires interface -> implementation. All handlers/routes request interfaces via
`FromDishka[...]` for injection.

## Notes for Future Work
- Keep adding protocols per domain in `app/interfaces/`.
- Use interfaces in controllers/handlers; keep concrete classes in adapters/controllers.
- When extending functionality, add providers in `app/ioc.py`.
