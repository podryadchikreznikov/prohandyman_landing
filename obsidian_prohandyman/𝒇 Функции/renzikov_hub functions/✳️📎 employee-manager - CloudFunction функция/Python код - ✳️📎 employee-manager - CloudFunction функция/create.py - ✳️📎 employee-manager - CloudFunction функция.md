
```python
import json
import os
import ydb
from utils import created, loads_safe
from custom_errors import AuthError, LogicError, NotFoundError

# Допустимые роли
ALLOWED_ROLES = {"OWNER", "ADMIN", "EMPLOYEE", "MANAGER", "SENIOR_FOREMAN", "FOREMAN", "DISPATCHER", "ACCOUNTANT"}

def create_employee(session, firms_table, auth_pool, user_id, firm_id, data):
    """
    Добавляет нового сотрудника в фирму.
    
    Args:
        session: YDB сессия для работы с таблицей фирм
        firms_table: Имя таблицы Users в базе фирм
        auth_pool: Пул сессий для работы с базой auth-data
        user_id: ID пользователя, выполняющего запрос (из auth-gate)
        firm_id: ID фирмы
        data: Данные запроса с полями email и roles
    """
    new_email = data.get('email')
    new_roles = data.get('roles', ["EMPLOYEE"])
    
    if not new_email:
        raise LogicError("Field 'email' is required for CREATE action.")
    
    print(f"CREATE: Adding employee with email={new_email} to firm_id={firm_id}")
    
    # 1. Поиск пользователя в основной базе auth-data
    def find_user_by_email(auth_session):
        query_text = f"PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}'); DECLARE $email AS Utf8; SELECT user_id, user_name FROM users WHERE email = $email AND is_active = true;"
        query = auth_session.prepare(query_text)
        result_sets = auth_session.transaction(ydb.SerializableReadWrite()).execute(query, {'$email': new_email}, commit_tx=True)
        if not result_sets[0].rows:
            return None
        return result_sets[0].rows[0]
    
    target_user_data = auth_pool.retry_operation_sync(find_user_by_email)
    
    if not target_user_data:
        raise NotFoundError("User to be added not found or is not active.")
    
    target_user_id = target_user_data.user_id
    target_user_name = target_user_data.user_name
    
    print(f"Found user in auth-data: user_id={target_user_id}, name={target_user_name}")
    
    # 2. Добавление пользователя в фирму
    tx = session.transaction(ydb.SerializableReadWrite())
    
    # Проверка прав текущего пользователя
    admin_query = session.prepare(f"DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8; SELECT roles FROM `{firms_table}` WHERE user_id = $user_id AND firm_id = $firm_id;")
    admin_res = tx.execute(admin_query, {'$user_id': user_id, '$firm_id': firm_id})
    
    if not admin_res[0].rows:
        raise AuthError("Requesting user is not a member of the specified firm.")
    
    admin_roles = loads_safe(admin_res[0].rows[0].roles, default=[])
    if "ADMIN" not in admin_roles and "OWNER" not in admin_roles:
        raise AuthError("Insufficient permissions. Only ADMIN or OWNER can add employees.")

    # Валидация назначаемых ролей
    roles_set = set(new_roles or ["EMPLOYEE"])
    unknown = [r for r in roles_set if r not in ALLOWED_ROLES]
    if unknown:
        raise LogicError(f"Unknown roles: {unknown}")
    if "OWNER" in roles_set:
        raise LogicError("Role 'OWNER' cannot be assigned via this endpoint.")
    if "ADMIN" in roles_set and "OWNER" not in admin_roles:
        raise AuthError("Only OWNER can assign ADMIN role.")
    
    print(f"User {user_id} has sufficient permissions: {admin_roles}")
    
    # Проверка, не является ли пользователь уже членом фирмы
    check_query = session.prepare(f"DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8; SELECT 1 FROM `{firms_table}` WHERE user_id = $user_id AND firm_id = $firm_id;")
    check_res = tx.execute(check_query, {'$user_id': target_user_id, '$firm_id': firm_id})
    if check_res[0].rows:
        raise LogicError("This user is already a member of this firm.")
    
    # Вставка нового сотрудника
    insert_query = session.prepare(f"""
        DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8; DECLARE $email AS Utf8;
        DECLARE $full_name AS Utf8; DECLARE $roles AS Json;
        INSERT INTO `{firms_table}` (user_id, firm_id, email, password_hash, full_name, roles, is_active, created_at)
        VALUES ($user_id, $firm_id, $email, NULL, $full_name, $roles, true, CurrentUtcTimestamp());
    """)
    tx.execute(insert_query, {
        '$user_id': target_user_id,
        '$firm_id': firm_id,
        '$email': new_email,
        '$full_name': target_user_name,
        '$roles': json.dumps(sorted(list(roles_set)))
    })
    
    tx.commit()
    print(f"Successfully added employee {target_user_id} to firm {firm_id}")
    
    return created({
        "message": "Employee added successfully",
        "user_id": target_user_id
    })
```
