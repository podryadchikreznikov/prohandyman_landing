
```python
# index.py

import json, os, ydb
import ydb
from utils import parse_event, EventParseError, JsonLogger, loads_safe, ok, bad_request, forbidden, not_found, server_error, json_response
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa.loader import YcSaLoader
import get_logic
import update_logic
import storage_logic
from custom_errors import AuthError, LogicError, NotFoundError, QuotaExceededError

def check_permissions(session, user_id, firm_id):
    query_text = "DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8; SELECT roles FROM Users WHERE user_id = $user_id AND firm_id = $firm_id;"
    query = session.prepare(query_text)
    result = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$user_id": user_id, "$firm_id": firm_id}, commit_tx=True)
    if not result[0].rows:
        return (False, False)
    roles = loads_safe(result[0].rows[0].roles, default=[])
    is_admin_or_owner = "OWNER" in roles or "ADMIN" in roles
    return (True, is_admin_or_owner)

def handler(event, context):
    logger = JsonLogger()
    logger.info("request.received")
    try:
        # Извлекаем user_id из контекста авторизатора auth-gate
        try:
            authorizer = (event.get('requestContext') or {}).get('authorizer') or {}
            user_payload_str = authorizer.get('user_payload')
            if not user_payload_str:
                return forbidden("Authorization context missing")
            user_payload = loads_safe(user_payload_str)
            if not user_payload:
                return forbidden("Invalid authorization context")
            requesting_user_id = user_payload.get('user_id') or user_payload.get('sub')
            if not requesting_user_id:
                return forbidden("User ID not found in authorization context")
            logger.info("auth.ok", user_id=requesting_user_id)
        except KeyError:
            return forbidden("Invalid authorization context")
        
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
        # action из operationContext имеет приоритет над body
        action = (
            (event.get('requestContext') or {}).get('apiGateway', {})
            .get('operationContext', {})
            .get('action', data.get('action'))
        )
        logger.info("request.parsed", action=action, firm_id=firm_id)
        
        if not all([firm_id, action]):
            return bad_request("firm_id and action are required parameters.")

        # Получение YDB credentials из Lockbox
        secret_id = os.environ.get("YC_LOCKBOX_SECRET_ID")
        if not secret_id:
            raise RuntimeError("YC_LOCKBOX_SECRET_ID not configured")
        version_id = os.environ.get("YC_LOCKBOX_VERSION_ID")
        key_field = os.environ.get("YC_LOCKBOX_KEY_FIELD", "key.json")

        loader = YcSaLoader()
        lockbox_values = loader._read_lockbox_payload(secret_id=secret_id, version_id=version_id)
        sa_key = loader._extract_key_json(lockbox_values, key_field)
        ydb_creds = YcSaLoader.make_ydb_credentials_from_sa_key_dict(sa_key)

        firms_endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        firms_database = os.environ.get("YDB_DATABASE_FIRMS")
        tariffs_endpoint = os.environ.get("YDB_ENDPOINT_TARIFFS")
        tariffs_database = os.environ.get("YDB_DATABASE_TARIFFS")
        
        if not all([firms_endpoint, firms_database, tariffs_endpoint, tariffs_database]):
            raise RuntimeError("YDB endpoints or databases not configured")

        firms_pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)
        is_member, is_admin_or_owner = firms_pool.retry_operation_sync(
            lambda s: check_permissions(s, requesting_user_id, firm_id)
        )

        if not is_member:
            return forbidden("User is not a member of the specified firm.")

        tariffs_pool = get_session_pool(tariffs_endpoint, tariffs_database, credentials=ydb_creds)
        logger.info("router.ready", action=action)

        if action == 'GET_RECORD':
            if not is_admin_or_owner: return forbidden("Admin or Owner rights required for GET_RECORD.")
            return tariffs_pool.retry_operation_sync(lambda s: get_logic.get_or_create_record(s, firm_id))

        elif action == 'UPDATE_JSON':
            if not is_admin_or_owner: return forbidden("Admin or Owner rights required for UPDATE_JSON.")
            target_field = data.get('target_json_field')
            updates = data.get('updates')
            return tariffs_pool.retry_operation_sync(lambda s: update_logic.update_json_fields(s, firm_id, target_field, updates))

        elif action == 'CLEAR_JSON':
            if not is_admin_or_owner: return forbidden("Admin or Owner rights required for CLEAR_JSON.")
            fields = data.get('fields_to_clear')
            return tariffs_pool.retry_operation_sync(lambda s: update_logic.clear_json_fields(s, firm_id, fields))
        
        elif action == 'GET_UPLOAD_URL':
            filename = data.get('filename')
            filesize = data.get('filesize')
            return storage_logic.handle_get_upload_url(tariffs_pool, firm_id, filename, filesize)

        elif action == 'GET_DOWNLOAD_URL':
            file_key = data.get('file_key')
            return storage_logic.handle_get_download_url(firm_id, file_key)

        elif action == 'CONFIRM_UPLOAD':
            file_key = data.get('file_key')
            return storage_logic.handle_confirm_upload(tariffs_pool, firm_id, file_key)

        elif action == 'DELETE_FILE':
            file_key = data.get('file_key')
            return storage_logic.handle_delete_file(tariffs_pool, firm_id, file_key)

        else:
            return bad_request(f"Invalid action specified: '{action}'")

    except NotFoundError as e:
        return not_found(str(e))
    except QuotaExceededError as e:
        return json_response(413, {"message": str(e)})
    except Exception as e:
        logger.error("handler.internal_error", error=str(e))
        return server_error("Internal Server Error")
```