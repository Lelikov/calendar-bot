from app.clients.exceptions import (
    BaseAuthenticationError,
    BaseClientError,
    BaseRateLimitError,
    BaseValidationError,
)


class UnisenderGoError(BaseClientError):
    pass


class UnisenderGoAuthenticationError(UnisenderGoError, BaseAuthenticationError):
    pass


class UnisenderGoValidationError(UnisenderGoError, BaseValidationError):
    pass


class UnisenderGoRateLimitError(UnisenderGoError, BaseRateLimitError):
    pass
