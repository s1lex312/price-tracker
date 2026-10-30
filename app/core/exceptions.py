"""Application-level exceptions mapped to HTTP responses."""


class AppError(Exception):
    """Base application error with an HTTP status code."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """Requested resource does not exist."""

    status_code = 404
    detail = "Not found"


class BadRequestError(AppError):
    """Request payload failed business validation."""

    status_code = 400
    detail = "Bad request"


class AuthRequiredError(AppError):
    """Dashboard access requires an authenticated session."""

    status_code = 401
    detail = "Authentication required"


class ConflictError(AppError):
    """The requested operation conflicts with a running one."""

    status_code = 409
    detail = "Conflict"


class UnprocessableEntityError(AppError):
    """The request is well-formed but cannot be fulfilled right now."""

    status_code = 422
    detail = "Unprocessable entity"


class ExternalServiceError(AppError):
    """Upstream price source failed."""

    status_code = 502
    detail = "External service error"
