# utils/__init__.py
from .util_http.request import parse_event, EventParseError
from .util_http.response import ok, created, bad_request, unauthorized, forbidden, not_found, conflict, too_many, server_error, json_response
from .util_http.cors import cors_headers, handle_preflight
from .util_log.logger import JsonLogger
from .util_errors.exceptions import AppError, BadRequest, Unauthorized, Forbidden, NotFound, Conflict, RateLimited, Internal
from .util_errors.to_response import app_error_to_http
from .util_time.index import now_utc, parse_iso_utc, to_ts_us, from_ts_us, to_ts_ms, from_ts_ms
from .util_json.index import loads_safe, dumps_compact, is_json_like
from .util_crypto.password import hash_password, verify_password
from .util_crypto.jwt_tokens import issue_jwt, verify_jwt
from .util_ydb.driver import get_driver, get_session_pool, get_driver_from_env, get_session_pool_from_env

try:
    from .util_invoke.invoke import invoke_function, invoke_many
except ImportError:  # pragma: no cover - optional dependency
    def invoke_function(*args, **kwargs):
        raise ImportError("cloud_utils.util_invoke requires the 'requests' package; install it to enable invoke_function")  # noqa: N818

    def invoke_many(*args, **kwargs):
        raise ImportError("cloud_utils.util_invoke requires the 'requests' package; install it to enable invoke_many")

try:
    from .util_sms import send_sms_code, validate_phone_number
except ImportError:  # pragma: no cover - optional dependency
    def send_sms_code(*args, **kwargs):
        raise ImportError("cloud_utils.util_sms requires the 'requests' package; install it to enable send_sms_code")

    def validate_phone_number(*args, **kwargs):
        raise ImportError("cloud_utils.util_sms requires the 'requests' package; install it to enable validate_phone_number")
