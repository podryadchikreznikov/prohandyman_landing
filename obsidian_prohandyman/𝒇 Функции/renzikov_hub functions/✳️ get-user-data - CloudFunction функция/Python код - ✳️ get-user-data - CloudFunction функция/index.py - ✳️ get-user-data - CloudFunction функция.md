```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import traceback
from typing import Any, Dict, List, Optional

import ydb

from utils.util_log.logger import JsonLogger
from utils.util_http.cors import cors_headers, handle_preflight
from utils.util_http.request import parse_event, EventParseError
from utils.util_http.response import ok, bad_request, server_error
from utils.util_errors.exceptions import AppError, Unauthorized, NotFound, Internal
from utils.util_errors.to_response import app_error_to_http
from utils.util_json.index import loads_safe
from utils.util_ydb.credentials import ydb_creds_from_env
from utils.util_ydb.driver import get_session_pool
from utils.util_crypto.jwt_tokens import verify_jwt  # оставляем как альтернативу

logger = JsonLogger()

# Базовые заголовки (CORS + anti-cache)
BASE_HEADERS = {
    **cors_headers(allow_origin=os.getenv("CORS_ALLOW_ORIGIN", "*")),
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

def _with_base_headers(resp: Dict[str, Any]) -> Dict[str, Any]:
    headers = resp.get("headers") or {}
    resp["headers"] = {**BASE_HEADERS, **headers}
    return resp

def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        logger.error("config.env_missing", env=name)
        raise Internal("Service configuration error")
    return v

# ---------- АВТОРИЗАЦИЯ / ИДЕНТИФИКАЦИЯ ПОЛЬЗОВАТЕЛЯ ----------

def _auth_from_authorizer(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Если маршрут в шлюзе сконфигурирован с function-authorizer,
    API Gateway положит payload в requestContext.authorizer.user_payload.
    Иначе здесь будет None. См. доки по authorizer (Authorization context). 
    """
    authorizer = event.get("requestContext", {}).get("authorizer", {})
    user_payload_str = authorizer.get("user_payload")
    if not user_payload_str:
        return None
    payload = loads_safe(user_payload_str)
    return payload or None

def _auth_from_bearer(bearer: Optional[str]) -> Dict[str, Any]:
    """
    Альтернативный путь: если авторизатора нет или он не сработал —
    валидируем токен локально (подпись по JWT_SECRET), чтобы не ломать клиентов.
    """
    if not bearer:
        raise Unauthorized("Authorization context missing")

    secret = os.getenv("JWT_SECRET")
    if not secret:
        logger.error("config.jwt_secret_missing")
        # Это конфигурационная ошибка сервиса, не клиента
        raise Internal("Service misconfiguration: JWT secret is not set")

    try:
        payload = verify_jwt(bearer, secret=secret, verify_exp=False)
        return payload
    except Exception as e:
        logger.warn("auth.bearer_invalid", error=str(e))
        raise Unauthorized("Invalid or malformed token")

def _resolve_user_id(req: Dict[str, Any], event: Dict[str, Any]) -> str:
    """
    Приоритет, который ты запросил:
    1) Явно переданный user_id (query ?user_id= или body {"user_id": ...}) — БЕЗ АВТОРИЗАЦИИ.
    2) Если не передан — берём из authorizer (если маршрут со включённым authorizer).
    3) Если authorizer нет — пробуем Bearer JWT (локальная валидация).
    4) Если ничего нет — 400.
    """
    # 1) user_id в запросе
    body = (req.get("body_dict") or {})
    query = (req.get("query") or {})
    user_id = (body.get("user_id") or query.get("user_id") or "").strip()
    if user_id:
        return user_id

    # 2) authorizer → 3) bearer
    payload = _auth_from_authorizer(event)
    if payload is None:
        payload = _auth_from_bearer(req.get("bearer"))  # может бросить Unauthorized/Internal

    user_id = (payload.get("user_id") or payload.get("sub") or "").strip()
    if not user_id:
        logger.error("auth.user_id_missing_in_payload")
        raise Unauthorized("User ID not found in token")
    return user_id

def _get_user_info(session: ydb.Session, auth_database: str, user_id: str) -> Dict[str, Any]:
    q = f"""
        PRAGMA TablePathPrefix('{auth_database}');
        DECLARE $user_id AS Utf8;
        SELECT user_id, email, user_name
        FROM users
        WHERE user_id = $user_id;
    """
    rs = session.transaction(ydb.OnlineReadOnly()).execute(
        session.prepare(q),
        {"$user_id": user_id},
        commit_tx=True,
    )
    rows = rs[0].rows
    if not rows:
        raise NotFound("User not found")
    row = rows[0]
    return {"user_id": row.user_id, "email": row.email, "user_name": row.user_name}

def _get_user_firm_ids(session: ydb.Session, firms_database: str, user_id: str) -> List[str]:
    q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $user_id AS Utf8;
        SELECT firm_id
        FROM Users
        WHERE user_id = $user_id AND is_active = true;
    """
    rs = session.transaction(ydb.OnlineReadOnly()).execute(
        session.prepare(q),
        {"$user_id": user_id},
        commit_tx=True,
    )
    return [r.firm_id for r in rs[0].rows]

def _get_firms_by_ids(session: ydb.Session, firms_database: str, firm_ids: List[str]) -> List[Dict[str, Any]]:
    if not firm_ids:
        return []
    q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_ids AS List<Utf8>;
        SELECT firm_id, firm_name, owner_user_id, integrations
        FROM Firms
        WHERE firm_id IN $firm_ids;
    """
    rs = session.transaction(ydb.OnlineReadOnly()).execute(
        session.prepare(q),
        {"$firm_ids": firm_ids},
        commit_tx=True,
    )
    out: List[Dict[str, Any]] = []
    for r in rs[0].rows:
        out.append({
            "firm_id": r.firm_id,
            "firm_name": r.firm_name,
            "owner_user_id": r.owner_user_id,
            "integrations": r.integrations if hasattr(r, "integrations") else None,
        })
    return out


# ---------- HANDLER ----------

def handler(event, context):
    # CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return _with_base_headers(handle_preflight(event))

    logger.info("get_user_data.invoked")

    # 1) Парсим вход (parse_event нормализует заголовки и извлекает bearer)
    try:
        req = parse_event(event)
    except EventParseError as e:
        logger.error("request.parse_error", error=str(e))
        return _with_base_headers(bad_request(str(e)))

    # 2) Определяем user_id согласно приоритету (см. _resolve_user_id)
    try:
        user_id = _resolve_user_id(req, event)
    except AppError as e:
        return _with_base_headers(app_error_to_http(e))
    except Exception as e:
        print(json.dumps({
            "level": "ERROR",
            "event": "get_user_data.auth_unexpected",
            "error": str(e),
            "trace": traceback.format_exc()
        }, ensure_ascii=False))
        return _with_base_headers(server_error("Internal Server Error"))

    # 3) Подключения к YDB
    try:
        ydb_creds = ydb_creds_from_env()
        auth_endpoint   = _require_env("YDB_ENDPOINT")
        auth_database   = _require_env("YDB_DATABASE")
        firms_endpoint  = _require_env("YDB_ENDPOINT_FIRMS")
        firms_database  = _require_env("YDB_DATABASE_FIRMS")

        auth_pool  = get_session_pool(auth_endpoint,  auth_database,  credentials=ydb_creds)
        firms_pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)
    except AppError as e:
        return _with_base_headers(app_error_to_http(e))
    except Exception as e:
        print(json.dumps({
            "level": "ERROR",
            "event": "get_user_data.db_connect_error",
            "error": str(e),
            "trace": traceback.format_exc()
        }, ensure_ascii=False))
        return _with_base_headers(server_error("Internal Server Error"))

    # 4) Запросы
    try:
        user_info = auth_pool.retry_operation_sync(lambda s: _get_user_info(s, auth_database, user_id))
        firm_ids  = firms_pool.retry_operation_sync(lambda s: _get_user_firm_ids(s, firms_database, user_id))
        firms     = firms_pool.retry_operation_sync(lambda s: _get_firms_by_ids(s, firms_database, firm_ids))

        resp = {
            "user_id":   user_info["user_id"],
            "email":     user_info["email"],
            "user_name": user_info.get("user_name"),
            "firms":     firms
        }
        logger.info("get_user_data.success", user_id=user_id, firms=len(firms))
        return _with_base_headers(ok(resp))

    except AppError as e:
        logger.warn("get_user_data.app_error", user_id=user_id, error=str(e))
        return _with_base_headers(app_error_to_http(e))
    except Exception as e:
        print(json.dumps({
            "level": "ERROR",
            "event": "get_user_data.unexpected",
            "user_id": user_id,
            "error": str(e),
            "trace": traceback.format_exc()
        }, ensure_ascii=False))
        return _with_base_headers(server_error("Internal Server Error"))
```