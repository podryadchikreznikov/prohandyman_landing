
```python
import datetime
import ydb
from utils import ok
from custom_errors import LogicError
from create_code import check_user_permissions, generate_code_value

def handle_get_instant_code(user_id, data, invitations_pool, firms_pool, logger):
    """Получает или создаёт краткосрочный код (10 минут)."""
    firm_id = data.get('firm_id')
    
    if not firm_id:
        raise LogicError("firm_id is required")
    
    # Проверка прав
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    def tx_get_or_create_instant(session: ydb.Session):
        table_path = f"invitation_codes/instant_code_{firm_id}"
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Создание таблицы если не существует
        try:
            session.create_table(
                table_path,
                ydb.TableDescription()
                .with_column(ydb.Column('firm_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('code_value', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('created_at', ydb.OptionalType(ydb.PrimitiveType.Timestamp)))
                .with_column(ydb.Column('expires_at', ydb.OptionalType(ydb.PrimitiveType.Timestamp)))
                .with_primary_key('firm_id')
            )
            logger.info("get_instant_code.table_created", firm_id=firm_id)
        except ydb.SchemeError:
            pass
        
        # Проверка существующего кода
        select_query = session.prepare(f"""
            DECLARE $firm_id AS Utf8;
            SELECT code_value, expires_at FROM `{table_path}` WHERE firm_id = $firm_id;
        """)
        
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            select_query,
            {'$firm_id': firm_id},
            commit_tx=False
        )
        
        # Если код существует и не истёк
        if result[0].rows:
            row = result[0].rows[0]
            expires_at = row.expires_at
            
            # Проверяем истечение
            if isinstance(expires_at, int):
                expires_dt = datetime.datetime.fromtimestamp(expires_at / 1_000_000, tz=datetime.timezone.utc)
            else:
                expires_dt = expires_at
            
            if expires_dt > now:
                # Код ещё действителен
                session.transaction().rollback()
                return {
                    "code_value": row.code_value,
                    "expires_at": expires_dt
                }
        
        # Создание нового кода
        new_code = generate_code_value()
        new_expires = now + datetime.timedelta(minutes=10)
        
        upsert_query = session.prepare(f"""
            DECLARE $firm_id AS Utf8;
            DECLARE $code_value AS Utf8;
            DECLARE $created_at AS Timestamp;
            DECLARE $expires_at AS Timestamp;
            
            UPSERT INTO `{table_path}` (firm_id, code_value, created_at, expires_at)
            VALUES ($firm_id, $code_value, $created_at, $expires_at);
        """)
        
        session.transaction().execute(
            upsert_query,
            {
                '$firm_id': firm_id,
                '$code_value': new_code,
                '$created_at': now,
                '$expires_at': new_expires
            },
            commit_tx=True
        )
        
        return {
            "code_value": new_code,
            "expires_at": new_expires
        }
    
    result = invitations_pool.retry_operation_sync(tx_get_or_create_instant)
    
    logger.info("get_instant_code.success", firm_id=firm_id)
    
    return ok({
        "code_value": result["code_value"],
        "expires_at": result["expires_at"].isoformat()
    })
```
