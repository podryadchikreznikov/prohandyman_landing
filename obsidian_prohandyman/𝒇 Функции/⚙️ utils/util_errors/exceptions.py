from typing import Any, Dict, Optional

class AppError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int = 400, details: Optional[Dict[str, Any]] = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}
        self.retryable = retryable

class BadRequest(AppError):
    def __init__(self, message="Bad Request", **kw):
        super().__init__("bad_request", message, http_status=400, **kw)

class Unauthorized(AppError):
    def __init__(self, message="Unauthorized", **kw):
        super().__init__("unauthorized", message, http_status=401, **kw)

class Forbidden(AppError):
    def __init__(self, message="Forbidden", **kw):
        super().__init__("forbidden", message, http_status=403, **kw)

class NotFound(AppError):
    def __init__(self, message="Not Found", **kw):
        super().__init__("not_found", message, http_status=404, **kw)

class Conflict(AppError):
    def __init__(self, message="Conflict", **kw):
        super().__init__("conflict", message, http_status=409, **kw)

class RateLimited(AppError):
    def __init__(self, message="Too Many Requests", **kw):
        super().__init__("rate_limited", message, http_status=429, retryable=True, **kw)

class Internal(AppError):
    def __init__(self, message="Internal Error", **kw):
        super().__init__("internal", message, http_status=500, **kw)