
```python
import uuid
import datetime
import ydb
import json
from utils import ok, created, loads_safe
from custom_errors import LogicError, NotFoundError

def add_user_to_firm(user_id, firm_id, firms_pool, logger):
    """Добавляет пользователя в фирму как EMPLOYEE."""
    def tx_add(session: ydb.Session):
        # Проверяем, не является ли уже членом
        check_query = session.prepare("""
            DECLARE $user_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            SELECT user_id FROM Users WHERE user_id = $user_id AND firm_id = $firm_id;
        """)
        
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            check_query,
            {'$user_id': user_id, '$firm_id': firm_id},
            commit_tx=False
        )
        
        if result[0].rows:
            raise LogicError("User is already a member of this firm")
        
        # Получаем email и имя из jwt-database (здесь упрощено)
        # В реальности нужно подключение к jwt-database
        
        # Добавляем пользователя
        insert_query = session.prepare("""
            DECLARE $user_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $email AS Utf8;
            DECLARE $full_name AS Utf8;
            DECLARE $roles AS Json;
            DECLARE $is_active AS Bool;
            DECLARE $created_at AS Timestamp;
            
            UPSERT INTO Users (user_id, firm_id, email, full_name, roles, is_active, created_at)
            VALUES ($user_id, $firm_id, $email, $full_name, $roles, $is_active, $created_at);
        """)
        
        now = datetime.datetime.now(datetime.timezone.utc)
        
        session.transaction().execute(
            insert_query,
            {
                '$user_id': user_id,
                '$firm_id': firm_id,
                '$email': f"{user_id}@temp.local",  # Временно
                '$full_name': "New Employee",  # Временно
                '$roles': json.dumps(["EMPLOYEE"]),
                '$is_active': True,
                '$created_at': now
            },
            commit_tx=True
        )
    
    firms_pool.retry_operation_sync(tx_add)

def handle_join_request(user_id, data, invitations_pool, firms_pool, logger):
    """Обрабатывает запрос на присоединение по коду."""
    code_value = data.get('code_value')
    dispatcher_id = data.get('dispatcher_id')
    
    if not code_value:
        raise LogicError("code_value is required")
    
    # Поиск кода в базе
    def tx_find_code(session: ydb.Session):
        # Ищем код во всех таблицах codes_*
        # Упрощённая версия - нужно сканировать таблицы
        # Здесь предполагаем, что передан также firm_id или код уникален
        
        # Для демонстрации: предполагаем, что можем найти по значению
        # В реальной реализации нужен более эффективный подход
        
        raise NotFoundError("Code search not implemented - need firm_id or global index")
    
    # Временно требуем firm_id для поиска
    firm_id = data.get('firm_id')
    if not firm_id:
        raise LogicError("firm_id is required for code lookup")
    
    def tx_process_code(session: ydb.Session):
        table_path = f"invitation_codes/codes_{firm_id}"
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Поиск кода
        query = session.prepare(f"""
            DECLARE $code_value AS Utf8;
            SELECT * FROM `{table_path}` WHERE code_value = $code_value AND is_active = true;
        """)
        
        result = session.transaction(ydb.SerializableReadWrite()).execute(
            query,
            {'$code_value': code_value},
            commit_tx=False
        )
        
        if not result[0].rows:
            raise NotFoundError("Invalid or inactive code")
        
        code = result[0].rows[0]
        
        # Проверка истечения
        expires_at = code.expires_at
        if isinstance(expires_at, int):
            expires_dt = datetime.datetime.fromtimestamp(expires_at / 1_000_000, tz=datetime.timezone.utc)
        else:
            expires_dt = expires_at
        
        if expires_dt < now:
            raise LogicError("Code has expired")
        
        # Проверка лимита использований
        if code.max_usage_count != -1 and code.current_usage >= code.max_usage_count:
            raise LogicError("Code usage limit reached")
        
        # Увеличиваем счётчик использований
        update_query = session.prepare(f"""
            DECLARE $code_id AS Utf8;
            UPDATE `{table_path}` SET current_usage = current_usage + 1 WHERE code_id = $code_id;
        """)
        
        session.transaction().execute(
            update_query,
            {'$code_id': code.code_id},
            commit_tx=True
        )
        
        return {
            'code_id': code.code_id,
            'firm_id': code.firm_id,
            'is_instant': code.is_instant
        }
    
    code_info = invitations_pool.retry_operation_sync(tx_process_code)
    
    # Если моментальный код - добавляем сразу
    if code_info['is_instant']:
        add_user_to_firm(user_id, code_info['firm_id'], firms_pool, logger)
        logger.info("join_request.instant_join", user_id=user_id, firm_id=code_info['firm_id'])
        return created({
            "message": "Successfully joined the firm",
            "firm_id": code_info['firm_id']
        })
    
    # Иначе создаём запрос на присоединение
    request_id = str(uuid.uuid4())
    
    def tx_create_request(session: ydb.Session):
        table_path = f"join_requests/requests_{code_info['firm_id']}_{code_info['code_id']}"
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Создание таблицы если не существует
        try:
            session.create_table(
                table_path,
                ydb.TableDescription()
                .with_column(ydb.Column('request_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('code_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('firm_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('user_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('requested_at', ydb.OptionalType(ydb.PrimitiveType.Timestamp)))
                .with_column(ydb.Column('dispatcher_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('likes_count_at_request', ydb.OptionalType(ydb.PrimitiveType.Int32)))
                .with_column(ydb.Column('dislikes_count_at_request', ydb.OptionalType(ydb.PrimitiveType.Int32)))
                .with_column(ydb.Column('blocks_count_at_request', ydb.OptionalType(ydb.PrimitiveType.Int32)))
                .with_column(ydb.Column('status', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('processed_at', ydb.OptionalType(ydb.PrimitiveType.Timestamp)))
                .with_column(ydb.Column('processed_by_user_id', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_column(ydb.Column('rejection_reason', ydb.OptionalType(ydb.PrimitiveType.Utf8)))
                .with_primary_key('request_id')
            )
        except ydb.SchemeError:
            pass
        
        # Вставка запроса
        insert_query = session.prepare(f"""
            DECLARE $request_id AS Utf8;
            DECLARE $code_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $requested_at AS Timestamp;
            DECLARE $dispatcher_id AS Utf8;
            DECLARE $likes_count AS Int32;
            DECLARE $dislikes_count AS Int32;
            DECLARE $blocks_count AS Int32;
            DECLARE $status AS Utf8;
            
            UPSERT INTO `{table_path}` (
                request_id, code_id, firm_id, user_id, requested_at,
                dispatcher_id, likes_count_at_request, dislikes_count_at_request,
                blocks_count_at_request, status
            ) VALUES (
                $request_id, $code_id, $firm_id, $user_id, $requested_at,
                $dispatcher_id, $likes_count, $dislikes_count, $blocks_count, $status
            );
        """)
        
        session.transaction(ydb.SerializableReadWrite()).execute(
            insert_query,
            {
                '$request_id': request_id,
                '$code_id': code_info['code_id'],
                '$firm_id': code_info['firm_id'],
                '$user_id': user_id,
                '$requested_at': now,
                '$dispatcher_id': dispatcher_id or '',
                '$likes_count': 0,  # TODO: получить реальную статистику
                '$dislikes_count': 0,
                '$blocks_count': 0,
                '$status': "PENDING"
            },
            commit_tx=True
        )
    
    invitations_pool.retry_operation_sync(tx_create_request)
    
    logger.info("join_request.created", request_id=request_id, firm_id=code_info['firm_id'])
    
    return created({
        "message": "Join request created",
        "request_id": request_id,
        "firm_id": code_info['firm_id']
    })
```
