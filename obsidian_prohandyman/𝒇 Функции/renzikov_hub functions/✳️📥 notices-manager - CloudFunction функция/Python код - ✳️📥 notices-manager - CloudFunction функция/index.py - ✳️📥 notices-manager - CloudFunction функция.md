```python
import json
import os
import ydb
from utils import (
    parse_event,
    EventParseError,
    JsonLogger,
    app_error_to_http,
    ok,
    bad_request,
    server_error,
)
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa.loader import YcSaLoader

from get import get_notices
from archive import archive_notice
from mark_as_delivered import mark_notices_as_delivered
from custom_errors import AuthError, LogicError, NotFoundError

def _log_event_context(logger: JsonLogger, event, context):
    """Выводит в лог подробную информацию о входящем событии и контексте вызова."""
    try:
        snippet = json.dumps(event, default=str, ensure_ascii=False)[:10000] if event is not None else None
        logger.info("raw_event", snippet=snippet)
    except Exception:
        logger.info("raw_event_non_serialisable", event=str(event))
    if context is not None:
        logger.info(
            "context",
            request_id=getattr(context, "request_id", None),
            function=getattr(context, "function_name", None),
            memory_limit=getattr(context, "memory_limit_in_mb", None),
        )

def handler(event, context):
    logger = JsonLogger()
    _log_event_context(logger, event, context)
    
    user_id = "unknown"
    action = "unknown"
    try:
        # Извлекаем user_id из контекста авторизатора auth-gate
        try:
            authorizer = event.get('requestContext', {}).get('authorizer', {})
            user_payload_str = authorizer.get('user_payload')
            if not user_payload_str:
                raise AuthError("Authorization context missing")
            user_payload = json.loads(user_payload_str)
            user_id = user_payload.get('user_id') or user_payload.get('sub')
            if not user_id:
                raise AuthError("User ID not found in authorization context")
            logger.info("authorized_request", user_id=user_id)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warn("failed_parse_authorization_context", error=str(e))
            raise AuthError("Invalid authorization context")

        action = event.get('requestContext', {}).get('apiGateway', {}).get('operationContext', {}).get('action')
        
        if not action:
            raise LogicError("Action is a required parameter (must be set in API Gateway operation context).")
 
        logger.info("processing_action", action=action, user_id=user_id)
 
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

        notices_endpoint = os.environ.get("YDB_ENDPOINT_NOTICES")
        notices_database = os.environ.get("YDB_DATABASE_NOTICES")
        
        if not all([notices_endpoint, notices_database]):
            raise RuntimeError("YDB_ENDPOINT_NOTICES or YDB_DATABASE_NOTICES not configured")

        table_name = f"notices_{user_id}"
        notices_pool = get_session_pool(notices_endpoint, notices_database, credentials=ydb_creds)
        
        logger.info("routing_action", action=action, table=table_name)
 
        def notices_transaction_router(session):
            if action == "GET":
                notice_id = event.get('pathParams', {}).get('noticeId')
                page_str = event.get('queryStringParameters', {}).get('page', '0')
                get_archived_str = event.get('queryStringParameters', {}).get('get_archived', 'false')
                
                logger.info("GET_params", notice_id=notice_id, page=page_str, get_archived=get_archived_str)
                
                return get_notices(
                    session, table_name, notice_id,
                    int(page_str), get_archived_str.lower() == 'true'
                )
            
            try:
                req = parse_event(event)
                data = req.get("body_dict") or {}
            except EventParseError as e:
                raise LogicError(f"Failed to parse request body: {e}")
            logger.info("parsed_request_body", action=action, body_summary=str(data)[:2000])
 
            if action == "ARCHIVE":
                notice_id = data.get('notice_id')
                return archive_notice(session, table_name, notice_id)
            
            elif action == "MARK_AS_DELIVERED":
                notice_ids = data.get('notice_ids')
                return mark_notices_as_delivered(session, table_name, notice_ids)
            
            else:
                raise LogicError(f"Invalid action specified: '{action}'.")
 
        response = notices_pool.retry_operation_sync(notices_transaction_router)
        
        if response.get('statusCode') == 200:
            logger.info("action_completed", action=action, user_id=user_id)
        
        logger.info("response_to_return", response=response)
        return response
 
    except (AuthError, LogicError, NotFoundError) as e:
        logger.warn("app_error", error=str(e))
        # custom_errors map to util AppError subclasses — convert to HTTP via util
        try:
            return app_error_to_http(e)
        except Exception:
            return bad_request(str(e))
    except Exception as e:
        logger.error("critical_error", error=str(e), user_id=user_id, action=action)
        return server_error()
```
```