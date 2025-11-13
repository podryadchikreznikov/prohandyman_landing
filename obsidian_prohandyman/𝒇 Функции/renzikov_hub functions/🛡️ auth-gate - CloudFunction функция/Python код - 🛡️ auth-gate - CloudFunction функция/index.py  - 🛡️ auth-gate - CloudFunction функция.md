```python
from utils.util_log.logger import JsonLogger
from utils.util_json import loads_safe, dumps_compact
from utils.util_errors.exceptions import Unauthorized
from utils.util_crypto.jwt_tokens import verify_jwt
import os
import json
import ydb
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env
import fnmatch
import re


def _get_header_ci(headers: dict, name: str) -> str | None:
    """Достаёт заголовок без учёта регистра ключа."""
    if not headers:
        return None
    lname = name.lower()
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == lname:
            return v
    return None


_POLICY_CACHE = None


def _load_policy():
    """Загружает JSON-политику доступа из локального файла access_policy.json.
    Если файл отсутствует/повреждён — включает режим по умолчанию (allow_if_not_listed=True).
    """
    global _POLICY_CACHE
    if _POLICY_CACHE is not None:
        return _POLICY_CACHE
    try:
        base_dir = os.path.dirname(__file__)
        cfg_path = os.path.join(base_dir, "access_policy.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            _POLICY_CACHE = json.load(f)
    except Exception:
        _POLICY_CACHE = {"default": {"allow_if_not_listed": True}, "rules": []}
    return _POLICY_CACHE


def _get_req_meta(event):
    headers = event.get("headers", {}) or {}
    host = _get_header_ci(headers, "Host") or _get_header_ci(headers, "X-Forwarded-Host")
    method = (
        (event.get("requestContext", {}).get("http", {}) or {}).get("method")
        or event.get("httpMethod")
        or ""
    )
    path = (
        (event.get("requestContext", {}).get("http", {}) or {}).get("path")
        or event.get("rawPath")
        or event.get("path")
        or ""
    )
    return host, path, (method or "").upper()


def _get_operation_action(event) -> str | None:
    try:
        return (
            (event.get("requestContext") or {})
            .get("apiGateway", {})
            .get("operationContext", {})
            .get("action")
        )
    except Exception:
        return None


def _match_rule(policy: dict, host: str, path: str, method: str) -> dict | None:
    rules = policy.get("rules", []) or []
    if not (path):
        return None
    for r in rules:
        host_rule = r.get("host")
        method_rule = (r.get("method") or "").upper()
        host_ok = (not host_rule) or host_rule == "*" or host_rule == host
        method_ok = (not method_rule) or method_rule == "*" or method_rule == method
        path_rule = r.get("path") or ""
        path_ok = bool(path_rule) and fnmatch.fnmatch(path, path_rule)
        if host_ok and method_ok and path_ok:
            return r
    return None


def _extract_firm_id(event) -> str | None:
    # Предпочтительно: из pathParameters, затем из query
    path_params = event.get("pathParameters") or event.get("requestContext", {}).get("pathParameters") or {}
    if isinstance(path_params, dict):
        firm_id = path_params.get("firm_id")
        if firm_id:
            return firm_id
    params = event.get("queryStringParameters") or {}
    if isinstance(params, dict):
        fid = params.get("firm_id")
        if fid:
            return fid
    # Парсим из пути, если он есть: ожидаем шаблон /firms/{firm_id}/...
    host, path, method = _get_req_meta(event)
    if path:
        m = re.match(r"^/firms/([^/]+)/", path)
        if m:
            return m.group(1)
    return None


def _verify_token_in_database(user_id: str, token: str, ydb_creds) -> bool:
    """Проверяет, что токен совпадает с сохраненным в базе данных для данного пользователя."""
    endpoint = os.environ.get("YDB_ENDPOINT")
    database = os.environ.get("YDB_DATABASE")
    if not endpoint or not database:
        return False
    
    try:
        pool = get_session_pool(endpoint, database, credentials=ydb_creds)
        
        def tx(session):
            q = session.prepare(
                f"""
                PRAGMA TablePathPrefix('{database}');
                DECLARE $user_id AS Utf8;
                SELECT jwt_token FROM users WHERE user_id = $user_id;
                """
            )
            rs = session.transaction(ydb.SerializableReadWrite()).execute(
                q, {"$user_id": user_id}, commit_tx=True
            )
            if not rs or not rs[0].rows:
                return False
            stored_token = getattr(rs[0].rows[0], "jwt_token", None)
            return stored_token == token
        
        return pool.retry_operation_sync(tx)
    except Exception:
        return False


def _get_user_roles_for_firm(user_id: str, firm_id: str, ydb_creds) -> list[str]:
    """Получает список ролей пользователя в фирме из базы фирм (таблица Users)."""
    endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
    database = os.environ.get("YDB_DATABASE_FIRMS")
    if not endpoint or not database:
        raise Unauthorized("YDB firms connection not configured")

    pool = get_session_pool(endpoint, database, credentials=ydb_creds)

    def tx(session):
        q = session.prepare(
            """
            DECLARE $firm_id AS Utf8; DECLARE $user_id AS Utf8;
            SELECT roles FROM `Users` WHERE firm_id = $firm_id AND user_id = $user_id;
            """
        )
        rs = session.transaction(ydb.SerializableReadWrite()).execute(
            q, {"$firm_id": firm_id, "$user_id": user_id}, commit_tx=True
        )
        if not rs or not rs[0].rows:
            return []
        roles_json = rs[0].rows[0].roles
        roles = loads_safe(roles_json, default=[])
        return roles if isinstance(roles, list) else []

    return pool.retry_operation_sync(tx)


def handler(event, context):
    """
    Кастомный authorizer для Yandex API Gateway.
    Проверяет JWT из заголовка Authorization: Bearer <token>.
    Возвращает {"isAuthorized": True/False, "context": {...}}.
    """
    # Используем JsonLogger для структурированного логирования
    logger = JsonLogger(correlation_id=getattr(context, 'request_id', None))
    logger.info("auth_gate.start", function=getattr(context, 'function_name', None))

    try:
        # 1) Заголовки и извлечение Authorization
        headers = event.get("headers", {}) or {}
        raw_auth = _get_header_ci(headers, "Authorization") or ""
        if not isinstance(raw_auth, str):
            raw_auth = str(raw_auth or "")

        parts = raw_auth.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warn("auth_gate.invalid_format", reason="missing_or_invalid_bearer")
            raise Unauthorized("Missing or invalid 'Bearer' token format")

        token = parts[1].strip()
        if not token:
            logger.warn("auth_gate.empty_token")
            raise Unauthorized("Empty token after 'Bearer' prefix")

        # 2) Верификация JWT с использованием util_crypto
        jwt_secret = os.environ.get("JWT_SECRET")
        if not jwt_secret:
            logger.error("auth_gate.no_secret", reason="JWT_SECRET not configured")
            raise Unauthorized("JWT_SECRET not configured")

        # verify_jwt из util_crypto выбрасывает исключение при ошибке
        # ВАЖНО: verify_exp=True для проверки срока действия токена
        user_payload = verify_jwt(token, jwt_secret, verify_exp=True)
        
        if not user_payload or "user_id" not in user_payload:
            logger.warn("auth_gate.invalid_payload", reason="missing_user_id")
            raise Unauthorized("Invalid token payload")
        
        # 3) STATEFUL CHECK: Проверка токена в базе данных
        try:
            ydb_creds = ydb_creds_from_env()
        except Exception as e:
            logger.error("auth_gate.creds_error", error=str(e))
            raise Unauthorized("Database credentials not configured")
        
        # Проверяем, что токен совпадает с хранящимся в БД
        if not _verify_token_in_database(user_payload.get("user_id"), token, ydb_creds):
            logger.warn("auth_gate.token_mismatch", user_id=user_payload.get("user_id"), reason="Token not found or expired in database")
            raise Unauthorized("Token has been revoked or replaced")

        # 4) Загрузка политики и проверка доступа по маршруту
        policy = _load_policy()
        host, path, method = _get_req_meta(event)
        rule = _match_rule(policy, host, path, method)

        # Если маршрут не описан — разрешаем по умолчанию (только по JWT)
        if not rule and (policy.get("default", {}).get("allow_if_not_listed", True)):
            logger.info("auth_gate.allowed_default", user_id=user_payload.get("user_id"), host=host, path=path, method=method)
            authorizer_context = {"user_payload": dumps_compact(user_payload)}
            return {"isAuthorized": True, "context": authorizer_context}

        if rule:
            # Роли могут задаваться как общие (allowed_roles_any), так и покомандно (allowed_roles_by_action)
            action = _get_operation_action(event)
            allowed_roles = None
            by_action = rule.get("allowed_roles_by_action") or {}
            if action and action in by_action:
                allowed_roles = by_action.get(action)
            if not allowed_roles:
                allowed_roles = rule.get("allowed_roles_any") or []
            if allowed_roles:
                firm_id = _extract_firm_id(event)
                if not firm_id:
                    logger.warn("auth_gate.no_firm_id", host=host, path=path, method=method)
                    return {"isAuthorized": False}
                try:
                    user_roles = _get_user_roles_for_firm(user_payload.get("user_id"), firm_id, ydb_creds)
                except Exception as ee:
                    logger.error("auth_gate.roles_fetch_failed", error=str(ee))
                    return {"isAuthorized": False}

                if not any(r in allowed_roles for r in (user_roles or [])):
                    logger.warn("auth_gate.forbidden", required=allowed_roles, actual=user_roles)
                    return {"isAuthorized": False}

        # 5) Успешный ответ для API Gateway
        logger.info("auth_gate.success", user_id=user_payload.get("user_id"))
        authorizer_context = {"user_payload": dumps_compact(user_payload)}
        return {"isAuthorized": True, "context": authorizer_context}

    except Unauthorized as e:
        logger.warn("auth_gate.unauthorized", message=str(e))
        return {"isAuthorized": False}
    except Exception as e:
        logger.error("auth_gate.critical_error", error=str(e), error_type=type(e).__name__)
        return {"isAuthorized": False}
```