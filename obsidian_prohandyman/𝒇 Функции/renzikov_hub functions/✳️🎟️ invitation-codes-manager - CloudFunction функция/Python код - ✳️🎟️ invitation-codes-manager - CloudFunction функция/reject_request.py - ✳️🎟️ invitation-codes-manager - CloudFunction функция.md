
```python
import datetime
import ydb
from utils import ok
from custom_errors import LogicError, NotFoundError
from create_code import check_user_permissions

def handle_reject_request(user_id, data, invitations_pool, firms_pool, logger):
    """Отклоняет запрос на присоединение к фирме."""
    firm_id = data.get('firm_id')
    request_id = data.get('request_id')
    code_id = data.get('code_id')
    rejection_reason = data.get('rejection_reason', '')
    
    if not all([firm_id, request_id, code_id]):
        raise LogicError("firm_id, request_id and code_id are required")
    
    # Проверяем права пользователя
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    def tx_reject_request(session: ydb.Session):
        table_name = f"join_requests/requests_{firm_id}_{code_id}"
        
        # Получаем запрос
        select_query = f"""
        DECLARE $request_id AS Utf8;
        SELECT status FROM `{table_name}` WHERE request_id = $request_id;
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
        
        # Обновляем статус запроса
        now = datetime.datetime.now(datetime.timezone.utc)
        update_query = f"""
        DECLARE $request_id AS Utf8;
        DECLARE $status AS Utf8;
        DECLARE $processed_at AS Timestamp;
        DECLARE $processed_by_user_id AS Utf8;
        DECLARE $rejection_reason AS Utf8;
        
        UPDATE `{table_name}` 
        SET status = $status, processed_at = $processed_at, 
            processed_by_user_id = $processed_by_user_id, rejection_reason = $rejection_reason
        WHERE request_id = $request_id;
        """
        session.transaction().execute(
            session.prepare(update_query),
            {
                "$request_id": request_id,
                "$status": "REJECTED",
                "$processed_at": now,
                "$processed_by_user_id": user_id,
                "$rejection_reason": rejection_reason
            },
            commit_tx=True
        )
    
    invitations_pool.retry_operation_sync(tx_reject_request)
    
    logger.info("reject_request.success", request_id=request_id, firm_id=firm_id, rejected_by=user_id)
    
    return ok({"message": "Request rejected successfully"})
```
