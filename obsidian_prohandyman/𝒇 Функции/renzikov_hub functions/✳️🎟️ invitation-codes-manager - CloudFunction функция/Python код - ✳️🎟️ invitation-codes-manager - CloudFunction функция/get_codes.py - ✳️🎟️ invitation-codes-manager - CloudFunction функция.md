
```python
import ydb
import json
from utils import ok
from custom_errors import LogicError
from create_code import check_user_permissions

def handle_get_codes(user_id, data, invitations_pool, firms_pool, logger):
    """Получает список кодов приглашений фирмы."""
    firm_id = data.get('firm_id')
    include_inactive = data.get('include_inactive', False)
    
    if not firm_id:
        raise LogicError("firm_id is required")
    
    # Проверка прав
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    def tx_get_codes(session: ydb.Session):
        table_path = f"invitation_codes/codes_{firm_id}"
        
        if include_inactive:
            query = f"SELECT * FROM `{table_path}` ORDER BY created_at DESC;"
        else:
            query = f"SELECT * FROM `{table_path}` WHERE is_active = true ORDER BY created_at DESC;"
        
        try:
            result = session.transaction(ydb.SerializableReadWrite()).execute(
                session.prepare(query),
                commit_tx=True
            )
            return result[0].rows
        except ydb.SchemeError:
            # Таблица не существует - нет кодов
            return []
    
    rows = invitations_pool.retry_operation_sync(tx_get_codes)
    
    codes = []
    for row in rows:
        code = {
            "code_id": row.code_id,
            "code_value": row.code_value,
            "created_at": row.created_at.isoformat() if hasattr(row.created_at, 'isoformat') else str(row.created_at),
            "expires_at": row.expires_at.isoformat() if hasattr(row.expires_at, 'isoformat') else str(row.expires_at),
            "max_usage_count": row.max_usage_count,
            "current_usage": row.current_usage,
            "is_active": row.is_active,
            "is_instant": row.is_instant
        }
        if row.object_id:
            code["object_id"] = row.object_id
        if row.metadata_json:
            try:
                code["metadata"] = json.loads(row.metadata_json)
            except Exception:
                pass
        codes.append(code)
    
    logger.info("get_codes.success", firm_id=firm_id, count=len(codes))
    
    return ok({"codes": codes})
```
