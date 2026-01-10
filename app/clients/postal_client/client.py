import logging
from http import HTTPStatus
from types import TracebackType
from typing import Any, Self

import niquests
import structlog
from niquests import AsyncSession
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import (
    PostalAuthenticationError,
    PostalError,
    PostalRateLimitError,
    PostalValidationError,
)
from .models import SendMessageRequest, SendMessageResponse


logger = structlog.get_logger()


class PostalClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        session: AsyncSession | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = session
        self._owned_session = session is None

        self.logger = logger.bind(
            service="postal_client",
            api_url=self.api_url,
        )

    async def __aenter__(self) -> Self:
        if self._session is None:
            self._session = AsyncSession()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._owned_session and self._session:
            await self._session.close()

    async def send_message(
        self,
        request: SendMessageRequest,
    ) -> SendMessageResponse:
        self.logger.debug(
            "sending_message",
            to=request.to,
            subject=request.subject,
            has_attachments=bool(request.attachments),
        )

        payload = request.model_dump(exclude_none=True, by_alias=True)

        response_data = await self._make_request(
            method="POST",
            endpoint="/api/v1/send/message",
            json_data=payload,
        )
        data = response_data.pop("data")

        response = SendMessageResponse(**response_data, data=data)

        if response.is_success:
            self.logger.debug(
                "message_sent_successfully",
                message_id=response.message_id,
                subject=request.subject,
            )
            return response
        self.logger.debug(
            "message_sent_with_warnings",
            status=response.status,
            data=response.data,
        )
        raise PostalError(f"Message sent error: {response.data}")

    def _get_headers(self) -> dict[str, str]:
        return {
            "X-Server-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _handle_response_errors(self, response: niquests.Response) -> None:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self.logger.error("authentication_failed", status_code=HTTPStatus.UNAUTHORIZED)
            raise PostalAuthenticationError("Invalid API key")

        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            self.logger.warning("rate_limit_exceeded", status_code=HTTPStatus.TOO_MANY_REQUESTS)
            raise PostalRateLimitError("Rate limit exceeded")

        if response.status_code == HTTPStatus.UNPROCESSABLE_CONTENT:
            try:
                error_data = response.json()
                self.logger.error(
                    "validation_error",
                    status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
                    errors=error_data,
                )
            except Exception:
                error_data = response.text
                self.logger.exception("validation_error", status_code=HTTPStatus.UNPROCESSABLE_CONTENT)
            raise PostalValidationError(f"Validation error: {error_data}")

        if not response.ok:
            self.logger.error(
                "request_failed",
                status_code=response.status_code,
                response=response.text,
            )
            raise PostalError(
                f"Request failed with status {response.status_code}: {response.text}",
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((PostalRateLimitError, niquests.exceptions.RequestException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._session is None:
            raise RuntimeError("Client must be used as context manager")

        url = f"{self.api_url}/{endpoint.lstrip('/')}"

        self.logger.debug(
            "making_request",
            method=method,
            url=url,
            has_data=json_data is not None,
        )

        try:
            response = await self._session.request(
                method=method,
                url=url,
                json=json_data,
                headers=self._get_headers(),
                timeout=self.timeout,
            )

            self._handle_response_errors(response)

            response_data = response.json()

            self.logger.debug(
                "request_successful",
                method=method,
                url=url,
                status_code=response.status_code,
            )

        except niquests.exceptions.Timeout as e:
            self.logger.exception("request_timeout", method=method, url=url, error=str(e))
            raise PostalError(f"Request timeout: {e}") from e

        except niquests.exceptions.RequestException as e:
            self.logger.exception(
                "request_exception",
                method=method,
                url=url,
                error=str(e),
            )
            raise

        return response_data
