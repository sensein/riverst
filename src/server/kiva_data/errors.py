class KivaDataError(Exception):
    """Base class for data-layer errors."""


class NotFoundError(KivaDataError):
    pass


class ValidationError(KivaDataError):
    pass


class AuthorizationError(KivaDataError):
    pass


class ConflictError(KivaDataError):
    pass
