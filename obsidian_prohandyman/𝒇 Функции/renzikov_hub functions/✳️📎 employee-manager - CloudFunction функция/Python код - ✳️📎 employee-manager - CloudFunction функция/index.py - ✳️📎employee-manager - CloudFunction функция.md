
```python
import json
import os
import ydb
from utils import parse_event, EventParseError, loads_safe, forbidden, bad_request, not_found, server_error
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa.loader import YcSaLoader

from get import get_employee_info
from create import create_employee
from edit import edit_employee_roles
from delete import delete_employee
from custom_errors import AuthError, LogicError, NotFoundError

def _log_event_context(event, context):
    """Выводит в лог подробную информацию о входящем событии и контексте вызова."""
    try:
        print("RAW EVENT: %s" % json.dumps(event, default=str, ensure_ascii=False)[:10000])
    except Exception:
        print("RAW EVENT (non-json serialisable): %s" % event)
    
    if context is not None:
        print(
            "CONTEXT: request_id=%s | function=%s | memory_limit=%s" %
            (getattr(context, "request_id", None),
            getattr(context, "function_name", None),
            getattr(context, "memory_limit_in_mb", None))
        )

def handler(event, context):
    _log_event_context(event, context)
    
    user_id = "unknown"
    action = "unknown"
    try:
        # Извлекаем user_id из контекста авторизатора auth-gate
        try:
            authorizer = event.get('requestContext', {}).get('authorizer', {})
            user_payload_str = authorizer.get('user_payload')
            if not user_payload_str:
                raise AuthError("Authorization context missing")
            user_payload = loads_safe(user_payload_str)
            if not user_payload:
                raise AuthError("Invalid authorization context")
            user_id = user_payload.get('user_id') or user_payload.get('sub')
            if not user_id:
                raise AuthError("User ID not found in authorization context")
            print(f"Authorized request for user_id: {user_id} (from auth-gate context)")
        except (KeyError,) as e:
            print(f"Failed to parse authorization context: {e}")
            raise AuthError("Invalid authorization context")

        # Получаем action из operation context API Gateway
        action = event.get('requestContext', {}).get('apiGateway', {}).get('operationContext', {}).get('action')
        
        if not action:
            raise LogicError("Action is a required parameter (must be set in API Gateway operation context).")

        print(f"Processing action: {action} for user_id: {user_id}")

        # Получаем firm_id из pathParameters (приоритет), затем из query (GET), затем из body (fallback)
        firm_id = None
        data = {}
        
        path_params = event.get('pathParameters') or event.get('requestContext', {}).get('pathParameters') or {}
        if isinstance(path_params, dict):
            firm_id = path_params.get('firm_id') or firm_id
        
        if not firm_id and action == "GET":
            q = event.get('queryStringParameters') or {}
            if isinstance(q, dict):
                firm_id = q.get('firm_id')
                # Пробрасываем user_id_to_get из query
                try:
                    data = data or {}
                    if isinstance(q.get('user_id_to_get'), str):
                        data['user_id_to_get'] = q.get('user_id_to_get')
                except Exception:
                    pass
        
        if not firm_id:
            try:
                req = parse_event(event)
                data = req.get("body_dict") or {}
                firm_id = data.get('firm_id')
            except EventParseError as e:
                raise LogicError(f"Failed to parse request body: {e}")
        
        if not firm_id:
            raise LogicError("firm_id is required.")
        
        print(f"Parsed request: firm_id={firm_id}, action={action}, data={data}")

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
        
        if not all([firms_endpoint, firms_database]):
            raise RuntimeError("YDB_ENDPOINT_FIRMS or YDB_DATABASE_FIRMS not configured")

        # Настройка подключений к базам данных
        firms_table = "Users"
        
        # Пул для базы фирм
        firms_pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)
        
        # Пул для базы auth-data (нужен только для CREATE)
        auth_pool = None
        if action == "CREATE":
            auth_endpoint = os.environ.get("YDB_ENDPOINT")
            auth_database = os.environ.get("YDB_DATABASE")
            if not all([auth_endpoint, auth_database]):
                raise RuntimeError("YDB_ENDPOINT or YDB_DATABASE not configured")
            auth_pool = get_session_pool(auth_endpoint, auth_database, credentials=ydb_creds)
        
        print(f"Routing action '{action}' to firms table '{firms_table}'")

        def employee_transaction_router(session):
            if action == "GET":
                return get_employee_info(session, firms_table, user_id, firm_id, data)
            
            elif action == "CREATE":
                return create_employee(session, firms_table, auth_pool, user_id, firm_id, data)
            
            elif action == "EDIT":
                return edit_employee_roles(session, firms_table, user_id, firm_id, data)
            
            elif action == "DELETE":
                return delete_employee(session, firms_table, user_id, firm_id, data)
            
            else:
                raise LogicError(f"Invalid action specified: '{action}'. Valid actions: GET, CREATE, EDIT, DELETE.")

        response = firms_pool.retry_operation_sync(employee_transaction_router)
        
        if response.get('statusCode') in [200, 201]:
            print(f"Action '{action}' for user {user_id} completed successfully.")
        
        print(f"Response to be returned: {response}")
        return response

    except AuthError as e:
        print(f"[AUTH ERROR] {e}")
        return forbidden(str(e))
    except LogicError as e:
        print(f"[LOGIC ERROR] {e}")
        return bad_request(str(e))
    except NotFoundError as e:
        print(f"[NOT FOUND ERROR] {e}")
        return not_found(str(e))
    except Exception as e:
        print(f"[CRITICAL ERROR] Error processing employee request for user {user_id} on action {action}: {e}")
        return server_error("Internal Server Error")
```