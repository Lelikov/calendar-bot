from datetime import UTC, datetime
from typing import Any

import pytest

from app.controllers.notification import NotificationController
from app.dtos import BookingClientDTO, BookingDTO, CancellationRefund, TriggerEvent, UserDTO
from app.settings import Settings


def make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "base_webhook_url": "https://example.test/webhook",
        "bot_token": "test-bot-token",
        "cal_signature": "test-cal-signature",
        "jitsi_jwt_token": "test-jitsi-token",
        "meeting_jwt_aud": "test-aud",
        "meeting_jwt_iss": "test-iss",
        "postgres_dsn": "postgresql://user:pass@localhost/test",
        "shortner_url": "https://short.test",
        "from_email": "noreply@example.test",
        "email_api_url": "https://email.test",
        "email_api_key": "test-email-key",
        "telegram_my_token": "test-telegram-token",
        "admin_api_token": "test-admin-token",
        "chat_api_key": "test-chat-key",
        "chat_api_secret": "test-chat-secret",
        "chat_user_id_encryption_key": "test-chat-enc-key",
        "offer_url": "https://offer.test",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def make_user(**overrides: Any) -> UserDTO:
    defaults: dict[str, Any] = {
        "id": 1,
        "name": "Psychologist",
        "email": "psychologist@example.test",
        "locked": False,
        "time_zone": "Europe/Moscow",
    }
    defaults.update(overrides)
    return UserDTO(**defaults)


def make_booking(**overrides: Any) -> BookingDTO:
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    defaults: dict[str, Any] = {
        "created_at": now,
        "end_time": now,
        "ical_sequence": 0,
        "id": 1,
        "is_recorded": False,
        "paid": True,
        "responses": {"name": "Client", "email": "client@example.test"},
        "start_time": now,
        "status": "accepted",
        "title": "Consultation",
        "uid": "booking-uid",
        "client": BookingClientDTO(name="Client", email="client@example.test", time_zone="Europe/Moscow"),
    }
    defaults.update(overrides)
    return BookingDTO(**defaults)


class TestBuildRebookUrl:
    def test_commercial_booking_uses_personal_link(self) -> None:
        settings = make_settings(cal_public_url="https://booking.zhivaya.org")
        booking = make_booking(
            event_type_parent_id=42,
            event_type_slug="consultation",
            user=make_user(username="jane-doe"),
        )

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url == "https://booking.zhivaya.org/jane-doe/consultation"

    def test_commercial_url_strips_trailing_slash_from_base(self) -> None:
        settings = make_settings(cal_public_url="https://booking.zhivaya.org/")
        booking = make_booking(
            event_type_parent_id=42,
            event_type_slug="consultation",
            user=make_user(username="jane-doe"),
        )

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url == "https://booking.zhivaya.org/jane-doe/consultation"

    def test_social_booking_falls_back_to_social_url(self) -> None:
        settings = make_settings(social_booking_url="https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist")
        booking = make_booking(event_type_parent_id=None, event_type_slug="volunteer-psychologist", user=make_user())

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url == "https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist"

    def test_parent_id_set_but_slug_does_not_match_falls_back_to_social(self) -> None:
        settings = make_settings(social_booking_url="https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist")
        booking = make_booking(
            event_type_parent_id=42,
            event_type_slug="some-other-slug",
            user=make_user(username="jane-doe"),
        )

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url == "https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist"

    def test_missing_organizer_username_falls_back_to_social(self) -> None:
        settings = make_settings(social_booking_url="https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist")
        booking = make_booking(
            event_type_parent_id=42,
            event_type_slug="consultation",
            user=make_user(username=None),
        )

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url == "https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist"

    def test_missing_user_falls_back_to_social(self) -> None:
        settings = make_settings(social_booking_url="https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist")
        booking = make_booking(event_type_parent_id=42, event_type_slug="consultation", user=None)

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url == "https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist"

    def test_never_returns_empty_string(self) -> None:
        settings = make_settings()
        booking = make_booking(event_type_parent_id=None, event_type_slug=None, user=None)

        url = NotificationController.build_rebook_url(booking=booking, settings=settings)

        assert url


class FakeEmailController:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def send_email(
        self,
        to_email: str,
        subject: str | None = None,
        context: dict | None = None,
        template_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.calls.append(
            {
                "to_email": to_email,
                "subject": subject,
                "context": context,
                "template_id": template_id,
                "metadata": metadata,
            },
        )


@pytest.fixture
def email_controller() -> FakeEmailController:
    return FakeEmailController()


@pytest.fixture
def notification_controller(email_controller: FakeEmailController) -> NotificationController:
    return NotificationController(
        db=None,  # not used by the methods under test
        bot=None,  # not used by the methods under test
        settings=make_settings(),
        email_controller=email_controller,
    )


class TestClientCancellationEmailRebookUrl:
    async def test_commercial_tariff_cancellation_context_has_personal_rebook_url(
        self,
        notification_controller: NotificationController,
        email_controller: FakeEmailController,
    ) -> None:
        booking = make_booking(
            event_type_parent_id=42,
            event_type_slug="consultation",
            user=make_user(username="jane-doe"),
        )

        await notification_controller.notify_client_email(
            booking=booking,
            trigger_event=TriggerEvent.BOOKING_CANCELLED,
            refund=CancellationRefund.FULL,
        )

        assert len(email_controller.calls) == 1
        context = email_controller.calls[0]["context"]
        assert context["RebookUrl"] == "https://booking.zhivaya.org/jane-doe/consultation"

    async def test_social_tariff_cancellation_context_has_social_rebook_url(
        self,
        notification_controller: NotificationController,
        email_controller: FakeEmailController,
    ) -> None:
        booking = make_booking(event_type_parent_id=None, event_type_slug="volunteer-psychologist", user=make_user())

        await notification_controller.notify_client_email(
            booking=booking,
            trigger_event=TriggerEvent.BOOKING_CANCELLED,
            refund=CancellationRefund.NONE,
        )

        assert len(email_controller.calls) == 1
        context = email_controller.calls[0]["context"]
        assert context["RebookUrl"] == "https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist"

    async def test_default_cancelled_template_context_also_has_rebook_url(
        self,
        notification_controller: NotificationController,
        email_controller: FakeEmailController,
    ) -> None:
        booking = make_booking(event_type_parent_id=None, event_type_slug="volunteer-psychologist", user=make_user())

        await notification_controller.notify_client_email(
            booking=booking,
            trigger_event=TriggerEvent.BOOKING_CANCELLED,
            refund=None,
        )

        assert len(email_controller.calls) == 1
        context = email_controller.calls[0]["context"]
        assert context["RebookUrl"] == "https://booking.zhivaya.org/team/zhivaya/volunteer-psychologist"
