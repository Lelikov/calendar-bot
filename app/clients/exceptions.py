class BaseClientError(Exception):
    pass


class BaseAuthenticationError(BaseClientError):
    pass


class BaseValidationError(BaseClientError):
    pass


class BaseRateLimitError(BaseClientError):
    pass
