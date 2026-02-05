import logging
from abc import ABC, abstractmethod
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

from app.clients.exceptions import (
    BaseClientError,
    BaseRateLimitError,
)


logger = structlog.get_logger()


class BaseClient(ABC):
    def __init__(
        self,
        api_url: str,
        api_key: str,
        service_name: str,
        base_error_class: type[BaseClientError] = BaseClientError,
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
        self.base_error_class = base_error_class

        self.logger = logger.bind(
            service=service_name,
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

    @abstractmethod
    def _get_headers(self) -> dict[str, str]:
        """Return headers for the request."""

    @abstractmethod
    def _handle_response_errors(self, response: niquests.Response) -> None:
        """Handle response errors."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((BaseRateLimitError, niquests.exceptions.RequestException)),
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
            raise self.base_error_class(f"Request timeout: {e}") from e

        except niquests.exceptions.RequestException as e:
            self.logger.exception(
                "request_exception",
                method=method,
                url=url,
                error=str(e),
            )
            raise

        return response_data
