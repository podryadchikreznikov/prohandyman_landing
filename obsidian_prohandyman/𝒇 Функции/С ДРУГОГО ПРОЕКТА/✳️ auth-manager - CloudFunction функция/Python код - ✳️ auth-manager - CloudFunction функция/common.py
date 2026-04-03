# -*- coding: utf-8 -*-
import os
import random
import datetime
import ydb

CODE_EXPIRY_LOGIN_MINUTES = 5
CODE_EXPIRY_REGISTER_MINUTES = 10
CODE_RESEND_MINUTES = 3
YDB_TRANSPORT_TIMEOUT_SECONDS = 30.0
YDB_OPERATION_TIMEOUT_SECONDS = 29.5

VALID_ACTIONS = {
    "login",
    "register",
    "resend_code",
    "verify_code",
    "reset_password",
    "reset_sessions",
    "get_user_data",
}

DEFAULT_USERS_TABLE = "Users"
DEFAULT_DISPATCHERS_TABLE = "Dispatchers"


def normalize_timestamp(ts):
    """YDB может вернуть timestamp как int (микросекунды) или datetime."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.datetime.fromtimestamp(ts / 1_000_000, tz=datetime.timezone.utc)
    if isinstance(ts, datetime.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=datetime.timezone.utc)
    return None


def get_user_type(event) -> str:
    """Извлекает user_type из операционного контекста API Gateway."""
    try:
        return (
            (event.get("requestContext") or {})
            .get("apiGateway", {})
            .get("operationContext", {})
            .get("user_type", "user")
        )
    except Exception:
        return "user"


def get_table_name(user_type: str) -> str:
    """Возвращает имя таблицы в зависимости от типа пользователя."""
    users_table = (os.environ.get("AUTH_MANAGER_USERS_TABLE") or DEFAULT_USERS_TABLE).strip()
    dispatchers_table = (os.environ.get("AUTH_MANAGER_DISPATCHERS_TABLE") or DEFAULT_DISPATCHERS_TABLE).strip()
    return dispatchers_table if user_type == "dispatcher" else users_table


def generate_code() -> str:
    """Генерирует 6-значный код верификации."""
    return str(random.randint(100000, 999999))


def build_request_settings() -> ydb.BaseRequestSettings:
    """
    Централизованные таймауты YDB для auth-manager.
    transport timeout держим чуть выше operation timeout, по рекомендации YDB.
    """
    settings = ydb.BaseRequestSettings()
    settings = settings.with_timeout(YDB_TRANSPORT_TIMEOUT_SECONDS)
    settings = settings.with_operation_timeout(YDB_OPERATION_TIMEOUT_SECONDS)
    settings = settings.with_cancel_after(YDB_OPERATION_TIMEOUT_SECONDS)
    return settings