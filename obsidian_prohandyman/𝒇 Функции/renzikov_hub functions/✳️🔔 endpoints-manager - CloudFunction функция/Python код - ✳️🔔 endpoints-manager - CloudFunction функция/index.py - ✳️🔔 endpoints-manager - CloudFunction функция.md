
```python
# index.py

import json
import os
import ydb
from utils import parse_event, EventParseError, JsonLogger, loads_safe, bad_request, forbidden, not_found, server_error
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa.loader import YcSaLoader
import pprint

import add_endpoint
import delete_endpoint
import get_endpoint
import send_notification
from custom_errors import AuthError, LogicError, NotFoundError

def _log_event_context(event, context):
    pass

def handler(event, context):
    _log_event_context(event, context)
    logger = JsonLogger()
    try:
        # 1) Пытаемся получить action из контекста API Gateway (работает для внешних вызовов)
        action = (
            event.get('requestContext', {})
                 .get('apiGateway', {})
                 .get('operationContext', {})
                 .get('action')
        )

        # 2) Разбираем тело запроса (данные понадобятся в любом случае)
        try:
            req = parse_event(event)
            data = req.get("body_dict") or {}
        except EventParseError as e:
            return bad_request(f"Failed to parse request: {e}")

        # 3) Если из контекста ничего не получили (внутренний вызов триггера), берём action из тела
        if not action:
            action = data.get('action')

        logger.info("request.parsed", action=action)
        if not action:
            return bad_request("Action is a required parameter.")

        # --------- АВТОРИЗАЦИЯ ---------
        # Для пользовательских действий (ADD, DELETE, GET_LIST) user_id извлекается из контекста авторизатора.
        # Для внутреннего действия SEND авторизация не требуется.
        user_id = None
        if action in ('ADD', 'DELETE', 'GET_LIST'):
            try:
                authorizer = event.get('requestContext', {}).get('authorizer', {})
                user_payload_str = authorizer.get('user_payload')
                if not user_payload_str:
                    return forbidden("Authorization context missing")
                user_payload = loads_safe(user_payload_str)
                if not user_payload:
                    return forbidden("Invalid authorization context")
                user_id = user_payload.get('user_id') or user_payload.get('sub')
                if not user_id:
                    return forbidden("User ID not found in authorization context")
                logger.info("auth.ok", user_id=user_id)
            except KeyError:
                return forbidden("Invalid authorization context")
        else:
            logger.info("auth.skipped", action=action)

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

        endpoints_endpoint = os.environ.get("YDB_ENDPOINT_ENDPOINTS")
        endpoints_database = os.environ.get("YDB_DATABASE_ENDPOINTS")
        
        if not all([endpoints_endpoint, endpoints_database]):
            raise RuntimeError("YDB_ENDPOINT_ENDPOINTS or YDB_DATABASE_ENDPOINTS not configured")

        # --- Маршрутизация ---
        endpoints_pool = get_session_pool(endpoints_endpoint, endpoints_database, credentials=ydb_creds)
        logger.info("router.db_ready", db="endpoints")

        if action == 'ADD':
            if not user_id: return forbidden("Authorization is required for ADD action.")
            push_token = data.get('push_token')
            device_info = data.get('device_info', {})
            return add_endpoint.handle_add_endpoint(endpoints_pool, user_id, push_token, device_info)
        
        elif action == 'DELETE':
            if not user_id: return forbidden("Authorization is required for DELETE action.")
            push_token = data.get('push_token')
            return delete_endpoint.handle_delete_endpoint(endpoints_pool, push_token, user_id)

        elif action == 'GET_LIST':
            if not user_id: return forbidden("Authorization is required for GET_LIST action.")
            return get_endpoint.handle_get_endpoints(endpoints_pool, user_id)

        elif action == 'SEND':
            # Для SEND авторизация по JWT не нужна, т.к. это внутренний вызов,
            # и user_id_to_notify передается в теле.
            notices_endpoint = os.environ.get("YDB_ENDPOINT_NOTICES")
            notices_database = os.environ.get("YDB_DATABASE_NOTICES")
            if not all([notices_endpoint, notices_database]):
                raise RuntimeError("YDB_ENDPOINT_NOTICES or YDB_DATABASE_NOTICES not configured")
            notices_pool = get_session_pool(notices_endpoint, notices_database, credentials=ydb_creds)
            user_id_to_notify = data.get('user_id_to_notify')
            payload = data.get('payload')
            return send_notification.handle_send_notification(endpoints_pool, notices_pool, user_id_to_notify, payload)

        else:
            return bad_request(f"Invalid action specified: '{action}'.")

    except AuthError as e:
        return forbidden(str(e))
    except LogicError as e:
        return bad_request(str(e))
    except NotFoundError as e:
        return not_found(str(e))
    except Exception as e:
        logger.error("endpoints.internal_error", error=str(e))
        return server_error("Internal Server Error")
```