
```python
import ydb
from utils import ok
from custom_errors import LogicError
from create_code import check_user_permissions

def handle_delete_code(user_id, data, invitations_pool, firms_pool, logger):
    """Деактивирует код приглашения."""
    firm_id = data.get('firm_id')
    code_id = data.get('code_id')
    
    if not all([firm_id, code_id]):
        raise LogicError("firm_id and code_id are required")
    
    # Проверка прав
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    def tx_delete(session: ydb.Session):
        table_path = f"invitation_codes/codes_{firm_id}"
        
        query = session.prepare(f"""
            DECLARE $code_id AS Utf8;
            UPDATE `{table_path}` SET is_active = false WHERE code_id = $code_id;
        """)
        
        session.transaction(ydb.SerializableReadWrite()).execute(
            query,
            {'$code_id': code_id},
            commit_tx=True
        )
    
    invitations_pool.retry_operation_sync(tx_delete)
    
    logger.info("delete_code.success", code_id=code_id, firm_id=firm_id)
    
    return ok({"message": "Code deleted successfully"})
```
