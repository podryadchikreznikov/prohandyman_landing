
```python
import uuid
import datetime
import random
import string
import ydb
import json
from utils import created, loads_safe
from custom_errors import AuthError, LogicError

def check_user_permissions(user_id, firm_id, firms_pool, logger):
    """Проверяет, что пользователь является OWNER или ADMIN фирмы."""
    def tx_check(session):
        query = session.prepare("""
            DECLARE $user_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            SELECT roles FROM Users WHERE user_id = $user_id AND firm_id = $firm_id;
        """)
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            query,
            {'$user_id': user_id, '$firm_id': firm_id},
            commit_tx=True
        )
        if not result[0].rows:
            raise AuthError("User is not a member of this firm")
        
        roles = loads_safe(result[0].rows[0].roles, default=[])
        if "OWNER" not in roles and "ADMIN" not in roles:
            raise AuthError("Insufficient permissions. Owner or Admin role required.")
    
    firms_pool.retry_operation_sync(tx_check)

def generate_code_value():
    """Генерирует 8-значный код."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def handle_create_code(user_id, data, invitations_pool, firms_pool, logger):
    """Создаёт новый код приглашения."""
    firm_id = data.get('firm_id')
    max_usage_count = data.get('max_usage_count', -1)
    expires_in_hours = data.get('expires_in_hours', 168)  # 1 неделя по умолчанию
    is_instant = data.get('is_instant', False)
    object_id = data.get('object_id')
    metadata_json = data.get('metadata_json', {})
    
    if not firm_id:
        raise LogicError("firm_id is required")
    
    # Проверка прав
    check_user_permissions(user_id, firm_id, firms_pool, logger)
    
    # Генерация данных кода
    code_id = str(uuid.uuid4())
    code_value = generate_code_value()
    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(hours=expires_in_hours)
    
    def tx_create(session: ydb.Session):
        # Создание таблицы если не существует
        table_path = f"invitation_codes/codes_{firm_id}"
        try:
            session.create_table(
                table_path,
                ydb.TableDescription()
                .with_column(ydb.Column('code_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('code_value', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('firm_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('created_at', ydb.OptionalType(ydb.PrimitiveType.Timestamp)))
                .with_column(ydb.Column('created_by_user_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('expires_at', ydb.OptionalType(ydb.PrimitiveType.Timestamp)))
                .with_column(ydb.Column('max_usage_count', ydb.OptionalType(ydb.PrimitiveType.Int32)))
                .with_column(ydb.Column('current_usage', ydb.OptionalType(ydb.PrimitiveType.Int32)))
                .with_column(ydb.Column('is_active', ydb.OptionalType(ydb.PrimitiveType.Bool)))
                .with_column(ydb.Column('is_instant', ydb.OptionalType(ydb.PrimitiveType.Bool)))
                .with_column(ydb.Column('object_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('metadata_json', ydb.OptionalType(ydb.PrimitiveType.Json)))
                .with_primary_key('code_id')
            )
            logger.info("create_code.table_created", firm_id=firm_id)
        except ydb.SchemeError:
            # Таблица уже существует
            pass
        
        # Вставка кода
        query = session.prepare(f"""
            DECLARE $code_id AS Utf8;
            DECLARE $code_value AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $created_at AS Timestamp;
            DECLARE $created_by_user_id AS Utf8;
            DECLARE $expires_at AS Timestamp;
            DECLARE $max_usage_count AS Int32;
            DECLARE $current_usage AS Int32;
            DECLARE $is_active AS Bool;
            DECLARE $is_instant AS Bool;
            DECLARE $object_id AS Utf8;
            DECLARE $metadata_json AS Json;
            
            UPSERT INTO `{table_path}` (
                code_id, code_value, firm_id, created_at, created_by_user_id,
                expires_at, max_usage_count, current_usage, is_active, is_instant,
                object_id, metadata_json
            ) VALUES (
                $code_id, $code_value, $firm_id, $created_at, $created_by_user_id,
                $expires_at, $max_usage_count, $current_usage, $is_active, $is_instant,
                $object_id, $metadata_json
            );
        """)
        
        session.transaction(ydb.SerializableReadWrite()).execute(
            query,
            {
                '$code_id': code_id,
                '$code_value': code_value,
                '$firm_id': firm_id,
                '$created_at': now,
                '$created_by_user_id': user_id,
                '$expires_at': expires_at,
                '$max_usage_count': max_usage_count,
                '$current_usage': 0,
                '$is_active': True,
                '$is_instant': is_instant,
                '$object_id': object_id or '',
                '$metadata_json': json.dumps(metadata_json)
            },
            commit_tx=True
        )
    
    invitations_pool.retry_operation_sync(tx_create)
    
    logger.info("create_code.success", code_id=code_id, firm_id=firm_id)
    
    return created({
        "code_id": code_id,
        "code_value": code_value,
        "expires_at": expires_at.isoformat()
    })
```
