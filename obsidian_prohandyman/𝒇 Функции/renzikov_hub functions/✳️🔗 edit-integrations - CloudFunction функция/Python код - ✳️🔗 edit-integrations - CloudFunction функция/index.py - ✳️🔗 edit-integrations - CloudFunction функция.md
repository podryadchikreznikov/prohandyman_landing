
```python
import json, os
import ydb
from utils import (
    parse_event, EventParseError,
    JsonLogger,
    ok, bad_request, forbidden, not_found, server_error,
    loads_safe, now_utc,
    Forbidden, BadRequest, NotFound,
)
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa.loader import YcSaLoader

# Алиасы для единообразия
AuthError = Forbidden
LogicError = BadRequest
NotFoundError = NotFound

# ────────────────────────── HELPERS ──────────────────────────

# Новый helper для глубокого мерджа словарей
def _deep_merge_dict(dst: dict, src: dict):
    """
    Рекурсивно мерджит словарь `src` в `dst`.
    Если по ключу находятся два словаря — выполняем глубокий мердж,
    иначе значение из `src` перезаписывает значение в `dst`.
    """
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge_dict(dst[k], v)
        else:
            dst[k] = v


def _check_membership_and_role(session, user_id, firm_id):
    query = session.prepare("DECLARE $uid AS Utf8; DECLARE $fid AS Utf8; SELECT roles FROM Users WHERE user_id = $uid AND firm_id = $fid;")
    res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$uid": user_id, "$fid": firm_id}, commit_tx=True)
    if not res[0].rows:
        return (False, False)
    roles = loads_safe(res[0].rows[0].roles, default=[])
    is_admin_or_owner = "OWNER" in roles or "ADMIN" in roles
    return (True, is_admin_or_owner)


def _get_integrations(session, firm_id):
    q = session.prepare("DECLARE $fid AS Utf8; SELECT integrations_json FROM Firms WHERE firm_id = $fid;")
    res = session.transaction(ydb.SerializableReadWrite()).execute(q, {"$fid": firm_id}, commit_tx=True)
    if not res[0].rows:
        raise NotFoundError("Firm not found")
    return loads_safe(res[0].rows[0].integrations_json, default={})


def _upsert_integrations(session, firm_id, new_data: dict):
    current = _get_integrations(session, firm_id)
    _deep_merge_dict(current, new_data)  # глубокий мердж вместо поверхностного update
    new_json = json.dumps(current)
    now = now_utc()
    q = session.prepare("""
        DECLARE $fid AS Utf8; DECLARE $data AS Json; DECLARE $now AS Timestamp;
        UPDATE Firms SET integrations_json = $data, updated_at = $now WHERE firm_id = $fid;
    """)
    session.transaction(ydb.SerializableReadWrite()).execute(q, {"$fid": firm_id, "$data": new_json, "$now": now}, commit_tx=True)


def _delete_integrations(session, firm_id, keys_to_delete):
    current = _get_integrations(session, firm_id)
    for k in keys_to_delete:
        current.pop(k, None)
    new_json = json.dumps(current)
    now = now_utc()
    q = session.prepare("""
        DECLARE $fid AS Utf8; DECLARE $data AS Json; DECLARE $now AS Timestamp;
        UPDATE Firms SET integrations_json = $data, updated_at = $now WHERE firm_id = $fid;
    """)
    session.transaction(ydb.SerializableReadWrite()).execute(q, {"$fid": firm_id, "$data": new_json, "$now": now}, commit_tx=True)

# ────────────────────────── HANDLER ──────────────────────────

def handler(event, context):
    logger = JsonLogger()
    try:
        # 1. Авторизация через auth-gate (user_id из авторизатора)
        authorizer = (event.get('requestContext') or {}).get('authorizer') or {}
        user_payload_str = authorizer.get('user_payload')
        if not user_payload_str:
            return forbidden("Authorization context missing")
        user_payload = loads_safe(user_payload_str)
        if not user_payload:
            return forbidden("Invalid authorization context")
        user_id = user_payload.get('user_id') or user_payload.get('sub')
        if not user_id:
            return forbidden("User ID not found in authorization context")

        # 2. Парсинг тела + firm_id из pathParameters (приоритет)
        try:
            req = parse_event(event)
            data = req.get("body_dict") or {}
        except EventParseError as e:
            return bad_request(f"Failed to parse request: {e}")
        path_params = event.get('pathParameters') or (event.get('requestContext') or {}).get('pathParameters') or {}
        firm_id = None
        if isinstance(path_params, dict):
            firm_id = path_params.get('firm_id')
        if not firm_id:
            firm_id = data.get('firm_id')
        action = data.get('action')
        if not all([firm_id, action]):
            return bad_request("firm_id and action are required")

        # 3. Получение YDB credentials из Lockbox
        secret_id = os.environ.get("YC_LOCKBOX_SECRET_ID")
        if not secret_id:
            raise RuntimeError("YC_LOCKBOX_SECRET_ID not configured")
        version_id = os.environ.get("YC_LOCKBOX_VERSION_ID")
        key_field = os.environ.get("YC_LOCKBOX_KEY_FIELD", "key.json")

        loader = YcSaLoader()
        lockbox_values = loader._read_lockbox_payload(secret_id=secret_id, version_id=version_id)
        sa_key = loader._extract_key_json(lockbox_values, key_field)
        ydb_creds = YcSaLoader.make_ydb_credentials_from_sa_key_dict(sa_key)

        firms_endpoint = os.environ.get('YDB_ENDPOINT_FIRMS')
        firms_database = os.environ.get('YDB_DATABASE_FIRMS')
        if not all([firms_endpoint, firms_database]):
            raise RuntimeError("YDB_ENDPOINT_FIRMS or YDB_DATABASE_FIRMS not configured")

        # Подключаемся к БД фирм
        pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)

        def txn(session):
            is_member, is_admin_or_owner = _check_membership_and_role(session, user_id, firm_id)
            if not is_member:
                return forbidden("User is not a member of the specified firm")

            if action == 'GET':
                integrations = _get_integrations(session, firm_id)
                return ok({"integrations": integrations})

            elif action == 'UPSERT':
                if not is_admin_or_owner:
                    return forbidden("Admin or Owner rights required for UPSERT")
                payload = data.get('payload')
                if not isinstance(payload, dict):
                    return bad_request("payload must be an object for UPSERT")
                _upsert_integrations(session, firm_id, payload)
                return ok({"message": "Integrations updated"})

            elif action == 'DELETE':
                if not is_admin_or_owner:
                    return forbidden("Admin or Owner rights required for DELETE")
                keys = data.get('integration_keys') or []
                if not isinstance(keys, list):
                    return bad_request("integration_keys must be a list for DELETE")
                _delete_integrations(session, firm_id, keys)
                return ok({"message": "Integrations deleted"})

            else:
                return bad_request("Invalid action")

        return pool.retry_operation_sync(txn)

    except AuthError as e:
        return forbidden(str(e))
    except LogicError as e:
        return bad_request(str(e))
    except NotFoundError as e:
        return not_found(str(e))
    except Exception as e:
        logger = JsonLogger()
        logger.error("edit_integrations.internal_error", error=str(e))
        return server_error("Internal Server Error")
```