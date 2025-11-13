```python
import json
import os
import ydb
from utils import parse_event, EventParseError, JsonLogger, validate_phone_number, bad_request, unauthorized, not_found, server_error
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa.loader import YcSaLoader

# Импорт локальных модулей
from request_reset import handle_request_reset
from reset import handle_reset
from custom_errors import LogicError, NotFoundError, AuthError

def handler(event, context):
    logger = JsonLogger()
    try:
        # Сначала получаем action из контекста, как это делает API Gateway
        action = (
            event.get('requestContext', {})
                .get('apiGateway', {})
                .get('operationContext', {})
                .get('action')
        )

        try:
            req = parse_event(event)
            data = req.get("body_dict") or {}
        except EventParseError as e:
            return bad_request(f"Failed to parse request: {e}")
        email = (data.get('email') or '').strip().lower() if data.get('email') else None
        phone_number_raw = (data.get('phone_number') or '').strip() if data.get('phone_number') else None

        # Валидация и нормализация телефона
        phone_number = validate_phone_number(phone_number_raw) if phone_number_raw else None
        if phone_number_raw and not phone_number:
            return bad_request("Invalid phone number format.")

        if not action:
            return bad_request("`action` is required parameter.")
        
        if not email and not phone_number:
            return bad_request("Either `email` or `phone_number` is required.")

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

        endpoint = os.environ.get("YDB_ENDPOINT")
        database = os.environ.get("YDB_DATABASE")
        if not all([endpoint, database]):
            raise RuntimeError("YDB_ENDPOINT or YDB_DATABASE not configured")

        pool = get_session_pool(endpoint, database, credentials=ydb_creds) # Используем основную jwt-database

        def transaction_router(session):
            if action == 'REQUEST_RESET':
                return handle_request_reset(session, email, phone_number)

            elif action == 'RESET':
                new_password = data.get('new_password')
                current_password_hash = data.get('current_password_hash')
                if not all([new_password, current_password_hash]):
                    raise LogicError("`new_password` and `current_password_hash` are required for RESET action.")
                return handle_reset(session, email, phone_number, new_password, current_password_hash)

            else:
                return bad_request(f"Invalid action specified: '{action}'. Valid actions are 'REQUEST_RESET', 'RESET'.")

        return pool.retry_operation_sync(transaction_router)

    except LogicError as e:
        return bad_request(str(e))
    except AuthError as e:
        return unauthorized(str(e))
    except NotFoundError as e:
        return not_found(str(e))
    except Exception as e:
        logger.error("password_manager.internal_error", email=email, error=str(e))
        return server_error("Internal Server Error")
```