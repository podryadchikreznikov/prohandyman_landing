
```python
import json
import ydb
from utils import ok, loads_safe
from custom_errors import AuthError, LogicError, NotFoundError

ROLE_HIERARCHY = {"OWNER": 7, "ADMIN": 6, "MANAGER": 5, "SENIOR_FOREMAN": 4, "FOREMAN": 3, "DISPATCHER": 2, "ACCOUNTANT": 2, "EMPLOYEE": 1}
EDITABLE_ROLES = {"ADMIN", "MANAGER", "SENIOR_FOREMAN", "FOREMAN", "DISPATCHER", "ACCOUNTANT", "EMPLOYEE"}

def get_highest_role_score(roles_json_str: str) -> int:
    """Возвращает наивысший балл из списка ролей пользователя."""
    roles = loads_safe(roles_json_str, default=[])
    if not roles:
        return 0
    return max(ROLE_HIERARCHY.get(role, 0) for role in roles)

def edit_employee_roles(session, firms_table, user_id, firm_id, data):
    """
    Добавляет или удаляет роль у сотрудника.
    
    Args:
        session: YDB сессия для работы с таблицей фирм
        firms_table: Имя таблицы Users в базе фирм
        user_id: ID пользователя, выполняющего запрос (из auth-gate)
        firm_id: ID фирмы
        data: Данные запроса с полями user_id_to_edit, role, sub_action (ADD_ROLE/REMOVE_ROLE)
    """
    user_id_to_edit = data.get('user_id_to_edit')
    role_to_change = data.get('role')
    sub_action = data.get('sub_action')  # ADD_ROLE или REMOVE_ROLE
    
    if not user_id_to_edit:
        raise LogicError("Field 'user_id_to_edit' is required for EDIT action.")
    
    if not role_to_change:
        raise LogicError("Field 'role' is required for EDIT action.")
    
    if sub_action not in ["ADD_ROLE", "REMOVE_ROLE"]:
        raise LogicError("Field 'sub_action' must be either 'ADD_ROLE' or 'REMOVE_ROLE'.")
    
    if role_to_change not in EDITABLE_ROLES:
        raise LogicError(f"Role '{role_to_change}' cannot be managed. Only ADMIN and EMPLOYEE roles can be edited.")
    
    if user_id == user_id_to_edit:
        raise LogicError("You cannot edit your own roles.")
    
    print(f"EDIT: {sub_action} role={role_to_change} for user={user_id_to_edit} in firm={firm_id}")
    
    tx = session.transaction(ydb.SerializableReadWrite())
    
    # Получаем данные о текущем пользователе и целевом пользователе
    query = session.prepare(f"""
        DECLARE $firm_id AS Utf8; DECLARE $admin_id AS Utf8; DECLARE $target_id AS Utf8;
        SELECT user_id, roles FROM `{firms_table}` WHERE firm_id = $firm_id AND user_id IN ($admin_id, $target_id);
    """)
    res = tx.execute(query, {'$firm_id': firm_id, '$admin_id': user_id, '$target_id': user_id_to_edit})
    
    admin_data, target_data = None, None
    for row in res[0].rows:
        if row.user_id == user_id:
            admin_data = row
        if row.user_id == user_id_to_edit:
            target_data = row
    
    if not admin_data:
        raise NotFoundError("Requesting user not found in this firm.")
    
    if not target_data:
        raise NotFoundError("Target user not found in this firm.")
    
    admin_roles_list = loads_safe(admin_data.roles, default=[])
    if "ADMIN" not in admin_roles_list and "OWNER" not in admin_roles_list:
        raise AuthError("Insufficient permissions. Only ADMIN or OWNER can manage roles.")

    # Проверка, что целевой пользователь не является владельцем
    if "OWNER" in loads_safe(target_data.roles, default=[]):
        raise AuthError("The firm owner's roles cannot be edited.")
    
    # Проверка иерархии ролей
    admin_score = get_highest_role_score(admin_data.roles)
    target_score = get_highest_role_score(target_data.roles)
    
    if admin_score <= target_score:
        raise AuthError("Insufficient permissions. Your role must be higher than the target user's role.")
    
    if role_to_change == "OWNER":
        raise LogicError("Role 'OWNER' cannot be managed.")

    if role_to_change == "ADMIN" and "OWNER" not in admin_roles_list:
        raise AuthError("Only OWNER can add or remove ADMIN role.")

    print(f"Permission check passed: admin_score={admin_score}, target_score={target_score}")
    
    # Обновление ролей
    roles_set = set(loads_safe(target_data.roles, default=[]))
    
    if sub_action == "ADD_ROLE":
        if role_to_change in roles_set:
            raise LogicError(f"User already has the role '{role_to_change}'.")
        roles_set.add(role_to_change)
        action_msg = "added"
    elif sub_action == "REMOVE_ROLE":
        if role_to_change not in roles_set:
            raise LogicError(f"User does not have the role '{role_to_change}'.")
        roles_set.remove(role_to_change)
        action_msg = "removed"
    
    new_roles_json = json.dumps(sorted(list(roles_set)))
    
    update_query = session.prepare(f"""
        DECLARE $roles AS Json; DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8;
        UPDATE `{firms_table}` SET roles = $roles WHERE user_id = $user_id AND firm_id = $firm_id;
    """)
    tx.execute(update_query, {'$roles': new_roles_json, '$user_id': user_id_to_edit, '$firm_id': firm_id})
    tx.commit()
    
    print(f"Successfully {action_msg} role '{role_to_change}' for user {user_id_to_edit}")
    
    return ok({"message": f"Role '{role_to_change}' successfully {action_msg}."})
```

