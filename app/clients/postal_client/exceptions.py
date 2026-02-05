from app.clients.exceptions import (
    BaseAuthenticationError,
    BaseClientError,
    BaseRateLimitError,
    BaseValidationError,
)


class PostalError(BaseClientError):
    pass


class PostalAuthenticationError(PostalError, BaseAuthenticationError):
    pass


class PostalValidationError(PostalError, BaseValidationError):
    pass


class PostalRateLimitError(PostalError, BaseRateLimitError):
    pass
