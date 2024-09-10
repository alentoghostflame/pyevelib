__all__ = (
    "HTTPGeneric",
    "HTTPBadRequest",
    "HTTPUnauthorized",
    "HTTPForbidden",
    "HTTPNotFound",
    "SDEGeneric",
    "SDENotLoaded",
)


class HTTPGeneric(Exception):
    """A generic HTTP-related exception to raise. Subclassed by all other HTTP exceptions."""
    pass


class HTTPBadRequest(HTTPGeneric):
    """Represents error 400 bad request."""


class HTTPUnauthorized(HTTPGeneric):
    """Represents error 401 Unauthorized."""
    pass


class HTTPForbidden(HTTPGeneric):
    """Represents error 403 Forbidden."""
    pass


class HTTPNotFound(HTTPGeneric):
    """Represents error 404 Not Found."""
    pass


class SDEGeneric(Exception):
    """A generic SDE-related exception to raise, Subclassed by all other SDE-related exceptions."""


class SDENotLoaded(SDEGeneric):
    """Raised when a function requiring the SDE to be loaded is called when the SDE is not loaded."""

