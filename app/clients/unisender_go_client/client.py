from http import HTTPStatus

import niquests
from niquests import AsyncSession

from app.clients.base_client import BaseClient
from .exceptions import (
    UnisenderGoAuthenticationError,
    UnisenderGoError,
    UnisenderGoRateLimitError,
    UnisenderGoValidationError,
)
from .models import SendMessageRequest, SendMessageResponse


class UnisenderGoClient(BaseClient):
    def __init__(
        self,
        api_url: str,
        api_key: str,
        timeout: int = 30,
        max_retries: int = 3,
        session: AsyncSession | None = None,
    ) -> None:
        super().__init__(
            api_url=api_url,
            api_key=api_key,
            service_name="unisender_go_client",
            base_error_class=UnisenderGoError,
            timeout=timeout,
            max_retries=max_retries,
            session=session,
        )

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
            endpoint="/email/send.json",
            json_data=payload,
        )

        response = SendMessageResponse(**response_data)

        if response.is_success:
            self.logger.debug(
                "message_sent_successfully",
                message_id=response.message_id,
                subject=request.subject,
            )
            return response

        self.logger.error(
            "message_sent_failed",
            status=response.status,
            code=response.code,
            message=response.message,
        )
        raise UnisenderGoError(f"Message sent error: {response.message} (code: {response.code})")

    def _get_headers(self) -> dict[str, str]:
        return {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_response_errors(self, response: niquests.Response) -> None:
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            self.logger.error("authentication_failed", status_code=HTTPStatus.UNAUTHORIZED)
            raise UnisenderGoAuthenticationError("Invalid API key")

        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            self.logger.warning("rate_limit_exceeded", status_code=HTTPStatus.TOO_MANY_REQUESTS)
            raise UnisenderGoRateLimitError("Rate limit exceeded")

        if response.status_code == HTTPStatus.BAD_REQUEST:
            try:
                error_data = response.json()
                self.logger.error(
                    "validation_error",
                    status_code=HTTPStatus.BAD_REQUEST,
                    errors=error_data,
                )
            except Exception:
                error_data = response.text
                self.logger.exception("validation_error", status_code=HTTPStatus.BAD_REQUEST)
            raise UnisenderGoValidationError(f"Validation error: {error_data}")

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
            raise UnisenderGoValidationError(f"Validation error: {error_data}")

        if not response.ok:
            self.logger.error(
                "request_failed",
                status_code=response.status_code,
                response=response.text,
            )
            raise UnisenderGoError(
                f"Request failed with status {response.status_code}: {response.text}",
            )
