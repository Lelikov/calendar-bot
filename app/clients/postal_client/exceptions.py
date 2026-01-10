class PostalError(Exception):
    pass


class PostalAuthenticationError(PostalError):
    pass


class PostalValidationError(PostalError):
    pass


class PostalRateLimitError(PostalError):
    pass
