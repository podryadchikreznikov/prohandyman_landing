
```python
import json
import ydb
from utils import ok, loads_safe
from custom_errors import NotFoundError

def get_employee_info(session, firms_table, user_id, firm_id, data):
    """
    Получает информацию о сотруднике или списке всех сотрудников фирмы.
    
    Args:
        session: YDB сессия для работы с таблицей фирм
        firms_table: Имя таблицы Users в базе фирм
        user_id: ID пользователя, выполняющего запрос (из auth-gate)
        firm_id: ID фирмы
        data: Данные запроса с опциональным полем user_id_to_get
    """
    user_id_to_get = data.get('user_id_to_get')
    
    tx = session.transaction(ydb.SerializableReadWrite())
    
    if user_id_to_get:
        # Получение информации о конкретном пользователе
        print(f"GET: Fetching info for user={user_id_to_get} in firm={firm_id}")
        
        query = session.prepare(f"""
            DECLARE $firm_id AS Utf8; DECLARE $target_id AS Utf8;
            SELECT * FROM `{firms_table}` WHERE firm_id = $firm_id AND user_id = $target_id;
        """)
        res = tx.execute(query, {'$firm_id': firm_id, '$target_id': user_id_to_get})
        
        if not res[0].rows:
            raise NotFoundError("Target user not found in this firm.")
        
        target_data = res[0].rows[0]
        tx.commit()
        
        result = {
            "user_id": target_data.user_id,
            "firm_id": target_data.firm_id,
            "email": target_data.email,
            "full_name": target_data.full_name,
            "roles": loads_safe(target_data.roles, default=[]),
            "is_active": target_data.is_active,
            "created_at": str(target_data.created_at)
        }
        
        print(f"Successfully fetched info for user {user_id_to_get}")
        
        return ok({"data": result})
    else:
        # Получение списка всех сотрудников фирмы
        print(f"GET: Fetching all employees for firm={firm_id}")
        
        query = session.prepare(f"DECLARE $firm_id AS Utf8; SELECT * FROM `{firms_table}` WHERE firm_id = $firm_id;")
        res = tx.execute(query, {'$firm_id': firm_id})
        tx.commit()
        
        users_list = []
        for row in res[0].rows:
            users_list.append({
                "user_id": row.user_id,
                "email": row.email,
                "full_name": row.full_name,
                "roles": loads_safe(row.roles, default=[]),
                "is_active": row.is_active
            })
        
        print(f"Successfully fetched {len(users_list)} employees from firm {firm_id}")
        
        return ok({"data": users_list})
```
