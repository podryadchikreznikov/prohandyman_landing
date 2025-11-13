
```python
import datetime
import ydb
from utils import ok
from custom_errors import LogicError, NotFoundError
from create_code import check_user_permissions
from join_request import add_user_to_firm

def handle_approve_request(user_id, data, invitations_pool, firms_pool, logger):
    """Одобряет запрос на присоединение к фирме."""
    firm_id = data.get('firm_id')
    request_id = data.get('request_id')
    code_id = data.get('code_id')
    
    if not all([firm_id, request_id, code_id]):
        raise LogicError("firm_id, request_id and code_id are required")
    
    # Проверяем права пользователя
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    # Получаем информацию о запросе
    request_user_id = None
    
    def tx_get_request(session: ydb.Session):
        nonlocal request_user_id
        
        table_name = f"join_requests/requests_{firm_id}_{code_id}"
        
        # Получаем запрос
        select_query = f"""
        DECLARE $request_id AS Utf8;
        SELECT * FROM `{table_name}` WHERE request_id = $request_id;
        """
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            session.prepare(select_query),
            {"$request_id": request_id},
            commit_tx=False
        )
        
        if not result[0].rows:
            raise NotFoundError("Request not found")
        
        request = result[0].rows[0]
        if request.status != "PENDING":
            raise LogicError(f"Request already {request.status}")
        
        request_user_id = request.user_id
        
        # Обновляем статус запроса
        now = datetime.datetime.now(datetime.timezone.utc)
        update_query = f"""
        DECLARE $request_id AS Utf8;
        DECLARE $status AS Utf8;
        DECLARE $processed_at AS Timestamp;
        DECLARE $processed_by_user_id AS Utf8;
        
        UPDATE `{table_name}` 
        SET status = $status, processed_at = $processed_at, processed_by_user_id = $processed_by_user_id
        WHERE request_id = $request_id;
        """
        session.transaction().execute(
            session.prepare(update_query),
            {
                "$request_id": request_id,
                "$status": "APPROVED",
                "$processed_at": now,
                "$processed_by_user_id": user_id
            },
            commit_tx=True
        )
    
    invitations_pool.retry_operation_sync(tx_get_request)
    
    # Добавляем пользователя в фирму
    try:
        add_user_to_firm(request_user_id, firm_id, firms_pool, logger)
    except LogicError as e:
        # Если пользователь уже в фирме - это не критично
        logger.warning("approve_request.user_already_in_firm", user_id=request_user_id, firm_id=firm_id)
    
    logger.info("approve_request.success", request_id=request_id, firm_id=firm_id, approved_by=user_id)
    
    return ok({"message": "Request approved successfully"})
```
