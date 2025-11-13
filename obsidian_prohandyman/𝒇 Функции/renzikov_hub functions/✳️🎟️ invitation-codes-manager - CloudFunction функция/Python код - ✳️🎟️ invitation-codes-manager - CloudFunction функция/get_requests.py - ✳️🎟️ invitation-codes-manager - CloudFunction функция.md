
```python
import ydb
from utils import ok
from custom_errors import LogicError
from create_code import check_user_permissions

def handle_get_requests(user_id, data, invitations_pool, firms_pool, logger):
    """Получает список запросов на присоединение для конкретного кода."""
    firm_id = data.get('firm_id')
    code_id = data.get('code_id')
    status_filter = data.get('status', None)
    
    if not all([firm_id, code_id]):
        raise LogicError("firm_id and code_id are required")
    
    # Проверяем права пользователя
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    # Получаем запросы
    def tx_get_requests(session: ydb.Session):
        table_name = f"join_requests/requests_{firm_id}_{code_id}"
        
        if status_filter:
            query = f"""
            DECLARE $status AS Utf8;
            SELECT * FROM `{table_name}` WHERE status = $status ORDER BY requested_at DESC;
            """
            params = {"$status": status_filter}
        else:
            query = f"""
            SELECT * FROM `{table_name}` ORDER BY requested_at DESC;
            """
            params = {}
        
        try:
            result = session.transaction(ydb.SerializableReadWrite()).execute(
                session.prepare(query),
                params,
                commit_tx=True
            )
            return result[0].rows
        except ydb.SchemeError:
            # Таблица не существует - значит нет запросов
            return []
    
    rows = invitations_pool.retry_operation_sync(tx_get_requests)
    
    requests = []
    for row in rows:
        req = {
            "request_id": row.request_id,
            "code_id": row.code_id,
            "firm_id": row.firm_id,
            "user_id": row.user_id,
            "requested_at": row.requested_at.isoformat() if hasattr(row.requested_at, 'isoformat') else str(row.requested_at),
            "dispatcher_id": row.dispatcher_id if row.dispatcher_id else None,
            "likes_count_at_request": row.likes_count_at_request,
            "dislikes_count_at_request": row.dislikes_count_at_request,
            "blocks_count_at_request": row.blocks_count_at_request,
            "status": row.status
        }
        
        if row.processed_at:
            req["processed_at"] = row.processed_at.isoformat() if hasattr(row.processed_at, 'isoformat') else str(row.processed_at)
        if row.processed_by_user_id:
            req["processed_by_user_id"] = row.processed_by_user_id
        if row.rejection_reason:
            req["rejection_reason"] = row.rejection_reason
        
        requests.append(req)
    
    logger.info("get_requests.success", firm_id=firm_id, code_id=code_id, count=len(requests))
    
    return ok({"requests": requests})
```
