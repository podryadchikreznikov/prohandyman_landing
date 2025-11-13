
```python
import json
import ydb
from utils import ok, loads_safe
from custom_errors import AuthError, LogicError, NotFoundError

# Словарь для определения веса ролей
ROLE_HIERARCHY = {"OWNER": 7, "ADMIN": 6, "MANAGER": 5, "SENIOR_FOREMAN": 4, "FOREMAN": 3, "DISPATCHER": 2, "ACCOUNTANT": 2, "EMPLOYEE": 1}

def get_highest_role_score(roles_json_str: str) -> int:
    """Возвращает наивысший балл из списка ролей пользователя."""
    roles = loads_safe(roles_json_str, default=[])
    if not roles:
        return 0
    return max(ROLE_HIERARCHY.get(role, 0) for role in roles)

def delete_employee(session, firms_table, user_id, firm_id, data):
    """
    Удаляет сотрудника из фирмы.
    
    Args:
        session: YDB сессия для работы с таблицей фирм
        firms_table: Имя таблицы Users в базе фирм
        user_id: ID пользователя, выполняющего запрос (из auth-gate)
        firm_id: ID фирмы
        data: Данные запроса с полем user_id_to_delete
    """
    user_id_to_delete = data.get('user_id_to_delete')
    
    if not user_id_to_delete:
        raise LogicError("Field 'user_id_to_delete' is required for DELETE action.")
    
    if user_id == user_id_to_delete:
        raise LogicError("You cannot delete yourself.")
    
    print(f"DELETE: Removing user={user_id_to_delete} from firm={firm_id}")
    
    tx = session.transaction(ydb.SerializableReadWrite())
    
    # Получаем данные о текущем пользователе и целевом пользователе
    query = session.prepare(f"""
        DECLARE $admin_id AS Utf8; DECLARE $target_id AS Utf8; DECLARE $firm_id AS Utf8;
        SELECT user_id, roles FROM `{firms_table}` 
        WHERE firm_id = $firm_id AND user_id IN ($admin_id, $target_id);
    """)
    res = tx.execute(query, {
        '$admin_id': user_id,
        '$target_id': user_id_to_delete,
        '$firm_id': firm_id
    })
    
    admin_data, target_data = None, None
    for row in res[0].rows:
        if row.user_id == user_id:
            admin_data = row
        elif row.user_id == user_id_to_delete:
            target_data = row
    
    if not admin_data:
        raise NotFoundError("Requesting user (admin) not found in the specified firm.")
    
    if not target_data:
        raise NotFoundError("Target user to delete not found in the specified firm.")
    
    # Проверка безопасности и иерархии
    target_roles = loads_safe(target_data.roles, default=[])
    if "OWNER" in target_roles:
        raise AuthError("Cannot delete the firm owner.")
    
    admin_score = get_highest_role_score(admin_data.roles)
    target_score = get_highest_role_score(target_data.roles)
    
    if admin_score <= target_score:
        raise AuthError("Insufficient permissions: your role must be higher than the target user's role.")
    
    print(f"Permission check passed: admin_score={admin_score}, target_score={target_score}")
    
    # Физическое удаление пользователя из фирмы
    delete_query = session.prepare(f"""
        DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8;
        DELETE FROM `{firms_table}` WHERE user_id = $user_id AND firm_id = $firm_id;
    """)
    tx.execute(delete_query, {'$user_id': user_id_to_delete, '$firm_id': firm_id})
    tx.commit()
    
    print(f"Successfully deleted user {user_id_to_delete} from firm {firm_id}")
    
    return ok({"message": "Employee successfully deleted."})
```
