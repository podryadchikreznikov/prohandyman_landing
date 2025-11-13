
```python
import os
from utils import parse_event, EventParseError, JsonLogger, ok, bad_request, forbidden, not_found, server_error, loads_safe
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env
from custom_errors import AuthError, LogicError, NotFoundError

# Импорт обработчиков действий
from create_code import handle_create_code
from delete_code import handle_delete_code
from get_codes import handle_get_codes
from get_instant_code import handle_get_instant_code
from join_request import handle_join_request
from get_requests import handle_get_requests
from approve_request import handle_approve_request
from reject_request import handle_reject_request

def handler(event, context):
    """
    Главный обработчик для управления кодами приглашений и запросами.
    """
    logger = JsonLogger()
    logger.info("invitation_codes_manager.start")
    
    try:
        # 1. Извлечение user_id из контекста авторизатора (для действий, требующих авторизации)
        user_id = None
        try:
            authorizer = event.get('requestContext', {}).get('authorizer', {})
            user_payload_str = authorizer.get('user_payload')
            if user_payload_str:
                user_payload = loads_safe(user_payload_str)
                if user_payload:
                    user_id = user_payload.get('user_id') or user_payload.get('sub')
        except Exception:
            pass
        
        # 2. Получение action из операционного контекста
        action = (
            event.get('requestContext', {})
            .get('apiGateway', {})
            .get('operationContext', {})
            .get('action')
        )
        
        if not action:
            logger.error("missing_action")
            return bad_request("Action is required")
        
        # 3. Парсинг тела запроса
        try:
            req = parse_event(event)
            data = req.get('body_dict') or {}
        except EventParseError as e:
            logger.error("request.parse_error", error=str(e))
            return bad_request(f"Invalid request: {e}")
        
        # 4. Получение YDB credentials из переменной окружения SA_KEY_JSON
        try:
            ydb_creds = ydb_creds_from_env()
        except Exception as e:
            logger.error("creds_error", error=str(e))
            return server_error("Database credentials not configured")
        
        # 5. Создание пулов сессий
        invitations_endpoint = os.environ.get("YDB_ENDPOINT_INVITATIONS")
        invitations_database = os.environ.get("YDB_DATABASE_INVITATIONS")
        firms_endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        firms_database = os.environ.get("YDB_DATABASE_FIRMS")
        
        if not all([invitations_endpoint, invitations_database, firms_endpoint, firms_database]):
            raise RuntimeError("YDB endpoints or databases not configured")
        
        invitations_pool = get_session_pool(invitations_endpoint, invitations_database, credentials=ydb_creds)
        firms_pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)
        
        # 6. Маршрутизация по действиям
        if action == "CREATE_CODE":
            if not user_id:
                return forbidden("Authorization required")
            return handle_create_code(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "DELETE_CODE":
            if not user_id:
                return forbidden("Authorization required")
            return handle_delete_code(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "GET_CODES":
            if not user_id:
                return forbidden("Authorization required")
            return handle_get_codes(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "GET_INSTANT_CODE":
            if not user_id:
                return forbidden("Authorization required")
            return handle_get_instant_code(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "JOIN_REQUEST":
            if not user_id:
                return forbidden("Authorization required")
            return handle_join_request(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "GET_REQUESTS":
            if not user_id:
                return forbidden("Authorization required")
            return handle_get_requests(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "APPROVE_REQUEST":
            if not user_id:
                return forbidden("Authorization required")
            return handle_approve_request(user_id, data, invitations_pool, firms_pool, logger)
        
        elif action == "REJECT_REQUEST":
            if not user_id:
                return forbidden("Authorization required")
            return handle_reject_request(user_id, data, invitations_pool, firms_pool, logger)
        
        else:
            logger.error("unknown_action", action=action)
            return bad_request(f"Unknown action: {action}")
    
    except AuthError as e:
        logger.warn("auth_error", error=str(e))
        return forbidden(str(e))
    
    except LogicError as e:
        logger.warn("logic_error", error=str(e))
        return bad_request(str(e))
    
    except NotFoundError as e:
        logger.warn("not_found", error=str(e))
        return not_found(str(e))
    
    except Exception as e:
        logger.error("critical_error", error=str(e), exc_info=True)
        return server_error("Internal Server Error")
```
