# Project Context: calendar-bot

## Overview
Calendar-bot is a FastAPI + Aiogram service for consultation booking workflows. It processes booking events,
creates video meeting links, manages chat channels, sends email/Telegram notifications, and consumes external
webhooks (booking provider, email provider, Jitsi).

Architecture is interface-driven: domain protocols live in `app/interfaces`, while implementations are provided
through Dishka DI container (`app/ioc.py`) with `APP` and `REQUEST` scopes.

## Runtime & Entrypoints
- `app/main.py`
  - Creates FastAPI app and Dishka container (`AppProvider + FastapiProvider + AiogramProvider`).
  - Configures CORS and validation error handler.
  - Lifespan startup: logger setup, optional Sentry init, Telegram webhook/bootstrap startup.
  - Lifespan shutdown: disposes SQLAlchemy engine.
- `app/routes.py`
  - HTTP endpoints for booking events/reminders and external webhooks.
  - Booking events are processed in background tasks with a fresh `Scope.REQUEST` container.

## HTTP Routes
- `POST /booking`
  - Validates Cal.com signature (`x-cal-signature-256`) unless debug mode.
  - Schedules async background booking processing.
- `POST /booking/reminder`
  - Protected by `admin-api-token` header.
  - Triggers reminder notifications for a time window or a specific booking UID.
- `GET /webhook/mail`
  - Healthcheck endpoint.
- `POST /webhook/mail`
  - Validates Unisender webhook signature (MD5 auth check), then handles event.
- `POST /telegram`
  - Validates Telegram secret token, forwards update to Aiogram dispatcher.
- `POST /jitsi/webhook`
  - Validates JWT and forwards Jitsi event to webhook controller.

## Interfaces (Protocols)
Interfaces are grouped by domain in `app/interfaces` and re-exported from `app/interfaces/__init__.py`:
- Booking: `IBookingDatabaseAdapter`, `IBookingController`
- Booking constraints: `IBookingConstraintsAnalyzer`
- Chat: `IChatClient`, `IChatController`
- Meeting: `IMeetingController`, `IMeetWebhookController`, `INotificationStateController`
- Mail: `IEmailClient`, `IEmailController`, `IMailWebhookController`
- Notification: `INotificationController`
- Cache: `ICacheController`
- Infra: `ISqlExecutor`, `IUrlShortener`, `ITelegramController`

## Controllers
- `BookingController`
  - Main booking orchestration for events:
    - created, rescheduled, payment initiated (used as reassignment flow), cancelled.
  - Handles reminder sending with deduplication via notification state cache.
  - Performs booking constraints validation on create and can reject + delete invalid bookings.
  - Coordinates chat creation/deletion, meeting URL lifecycle, organizer/client notifications.
- `BookingConstraintsAnalyzer`
  - Enforces constraints:
    - minimum interval between bookings,
    - max bookings per month,
    - max bookings per year,
    - no overlapping future active consultation.
  - Returns structured rejection data (`reasons`, `rejection_type`, `available_from`, etc.).
- `MeetingController`
  - Generates/updates/deletes meeting URLs (including participant-specific links).
  - Uses shortener and booking metadata sync logic.
- `NotificationController`
  - Sends organizer/client email notifications and organizer Telegram notifications.
  - Renders message content with timezone and duration helpers.
  - Supports dedicated rejected-booking notification for client.
- `MeetWebhookController`
  - Processes Jitsi webhook events and uses notification state deduplication.
- `NotificationStateController`
  - Cache-backed idempotency helper (`was_notified`, `mark_notified`).
- `MailWebhookController`, `EmailController`, `ChatController`, `TelegramController`, `CacheController`
  - Thin wrappers over respective clients/integrations.

## Adapters & Integrations
- DB/SQL
  - `adapters/sql.py`: `SqlExecutor` over SQLAlchemy `AsyncSession`.
  - `adapters/db.py`: `BookingDatabaseAdapter` with booking/user queries and mutation methods.
- Messaging / Chat
  - `adapters/get_stream.py`: GetStream implementation of `IChatClient` (+ token/user-id encode/decode helpers).
- Meetings / URLs
  - `adapters/shortener.py`: URL shortener adapter for create/get/update/delete operations.
- Email
  - `adapters/email.py`: Unisender Go email client implementation.
- Cache
  - Redis is provided in IoC and consumed via `CacheController`.

## DI / IoC (Dishka)
`app/ioc.py` binds interfaces to concrete implementations and manages resource scopes:
- APP-scoped: `Settings`, `Bot`, DB engine/sessionmaker, Redis/cache controller, email client/controller,
  chat adapter/controller, shortener, telegram controller, mail webhook controller, notification state controller.
- REQUEST-scoped: DB session, SQL executor, booking DB adapter, meeting/notification controllers,
  booking constraints analyzer, booking controller, meet webhook controller.

All routes request dependencies via `FromDishka[...]`; some background processing explicitly creates a request
scope to resolve `IBookingController`.

## Important Behavioral Notes
- Booking processing is async/background and wrapped with structured logging context (`uid`, organizer/client email).
- Reminder notifications are deduplicated with TTL-based cache keys.
- Booking constraints can be toggled by settings (`is_enable_booking_constraints`).
- Signature/JWT checks are enforced for external webhook integrity.

## Notes for Future Changes
- Keep adding protocols first in `app/interfaces`, then implementations/controllers.
- Register every new implementation in `AppProvider` with correct scope.
- Prefer orchestration in controllers and keep adapters focused on external I/O.
