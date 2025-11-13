```python
import json
import os
import logging
import ydb
from utils import parse_event, bad_request, unauthorized, forbidden, server_error, json_response, verify_jwt, get_session_pool

# Импорт логических модулей
import precondition_checks
import deletion_logic
from custom_errors import AuthError, LogicError, PreconditionFailedError

# Настройка логирования
logging.getLogger().setLevel(logging.INFO)

def handler(event, context):
    try:
        # 1. Авторизация и парсинг
        req = parse_event(event)
        user_jwt = req.get("bearer")
        if not user_jwt:
            raise AuthError("Unauthorized: Missing Bearer token.")
        user_payload = verify_jwt(user_jwt, secret=os.environ["JWT_SECRET"])  # может бросить исключение
        if not user_payload or 'user_id' not in user_payload:
            raise AuthError("Invalid or expired token.")
        
        user_id = user_payload['user_id']
        
        data = req.get('body_dict', {})
        firm_id = data.get('firm_id')
        if not firm_id:
            raise LogicError("`firm_id` is required in the request body.")

        logging.info(f"--- STARTING DELETION PROCESS FOR FIRM {firm_id} BY OWNER {user_id} ---")

        # 2. Подключение к основной БД для транзакций
        firms_pool = get_session_pool(os.environ["YDB_ENDPOINT_FIRMS"], os.environ["YDB_DATABASE_FIRMS"])

        # 3. Фаза 1: Проверка всех предусловий
        logging.info("--- PHASE 1: PRECONDITION CHECKS ---")
        precondition_checks.run_all_checks(firms_pool, user_jwt, user_id, firm_id)
        logging.info("All precondition checks passed successfully.")

        # 4. Фаза 2: Поэтапное удаление
        logging.info("--- PHASE 2: STAGED DELETION ---")
        deletion_logic.run_all_deletions(firms_pool, user_jwt, user_id, firm_id)
        
        logging.info(f"--- FIRM {firm_id} DELETED SUCCESSFULLY ---")
        return json_response(200, {"message": "Firm and all associated data successfully deleted."})

    except AuthError as e:
        logging.error(f"Authorization error: {e}", exc_info=True)
        return forbidden(str(e))
    except LogicError as e:
        logging.error(f"Logic error: {e}", exc_info=True)
        return bad_request(str(e))
    except PreconditionFailedError as e:
        logging.error(f"Precondition failed: {e}", exc_info=True)
        return json_response(412, {"error": {"code": "precondition_failed", "message": str(e)}})
    except Exception as e:
        logging.error(f"Critical unhandled error: {e}", exc_info=True)
        return server_error("Internal Server Error")