```python
import json, os, uuid, datetime, pytz, logging
import ydb
from utils import parse_event, created, bad_request, unauthorized, server_error, conflict, verify_jwt, get_driver, get_session_pool, get_session_pool_from_env

logging.basicConfig(level=logging.INFO)

class LogicError(Exception): pass
class NotFoundError(Exception): pass

def handler(event, context):
    req = parse_event(event)
    bearer = req.get("bearer")
    if not bearer:
        return unauthorized("Unauthorized")
    try:
        user_payload = verify_jwt(bearer, secret=os.environ["JWT_SECRET"])
    except Exception:
        return unauthorized("Invalid token")

    try:
        data = req.get('body_dict', {})
    except Exception as e:
        logging.error(f"Request body processing error: {e}")
        return bad_request(str(e))

    firm_name = data.get('firm_name')
    if not firm_name:
        return bad_request("firm_name is required.")

    new_firm_id = str(uuid.uuid4())
    owner_user_id = user_payload['user_id']
    owner_email = user_payload['email']
    owner_user_name = "Unknown" # Значение по умолчанию

    try:
        auth_pool = get_session_pool_from_env() # Используем основную БД (YDB_ENDPOINT/YDB_DATABASE)
        def get_user_name(session):
            query_text = "DECLARE $user_id AS Utf8; SELECT user_name FROM users WHERE user_id = $user_id;"
            result = session.transaction(ydb.SerializableReadWrite()).execute(
                session.prepare(query_text), {"$user_id": owner_user_id}, commit_tx=True
            )
            if not result[0].rows:
                raise NotFoundError("Owner user not found in main auth database.")
            return result[0].rows[0].user_name
        
        owner_user_name = auth_pool.retry_operation_sync(get_user_name)

    except Exception as e:
        logging.error(f"Не удалось получить имя пользователя {owner_user_id} из основной БД: {e}", exc_info=True)

    try:
        pool = get_session_pool(
            os.environ["YDB_ENDPOINT_FIRMS"],
            os.environ["YDB_DATABASE_FIRMS"]
        )

        def create_firm_and_assign_owner(session):
            tx = session.transaction(ydb.SerializableReadWrite())
            now = datetime.datetime.now(pytz.utc)
            
            # --- ИСПРАВЛЕННАЯ ЛОГИКА ПРОВЕРКИ ---
            # Проверяем, является ли пользователь уже ВЛАДЕЛЬЦЕМ какой-либо фирмы.
            check_query_text = """
                DECLARE $user_id AS Utf8;
                SELECT 1 FROM Users 
                WHERE user_id = $user_id AND String::Contains(CAST(roles AS String), '"OWNER"');
            """
            res = tx.execute(session.prepare(check_query_text), {"$user_id": owner_user_id})
            if res[0].rows:
                raise LogicError("User is already an owner of a firm.")
            # --- КОНЕЦ ИСПРАВЛЕННОЙ ЛОГИКИ ---

            create_firm_query_text = """
                DECLARE $firm_id AS Utf8; DECLARE $firm_name AS Utf8; DECLARE $owner_user_id AS Utf8;
                DECLARE $created_at AS Timestamp; DECLARE $is_active AS Bool; DECLARE $integrations AS Json;
                INSERT INTO Firms (firm_id, firm_name, owner_user_id, integrations_json, created_at, is_active) 
                VALUES ($firm_id, $firm_name, $owner_user_id, $integrations, $created_at, $is_active);
            """
            tx.execute(session.prepare(create_firm_query_text), {
                "$firm_id": new_firm_id, "$firm_name": firm_name, "$owner_user_id": owner_user_id,
                "$integrations": json.dumps({}),
                "$created_at": now, "$is_active": True
            })

            create_owner_query_text = """
                DECLARE $user_id AS Utf8; DECLARE $firm_id AS Utf8; DECLARE $email AS Utf8;
                DECLARE $full_name AS Utf8; DECLARE $roles AS Json; DECLARE $is_active AS Bool;
                DECLARE $created_at AS Timestamp;
                INSERT INTO Users (user_id, firm_id, email, full_name, roles, is_active, created_at)
                VALUES ($user_id, $firm_id, $email, $full_name, $roles, $is_active, $created_at);
            """
            tx.execute(session.prepare(create_owner_query_text), {
                "$user_id": owner_user_id,
                "$firm_id": new_firm_id,
                "$email": owner_email,
                "$full_name": owner_user_name,
                "$roles": json.dumps(["OWNER"]),
                "$is_active": True,
                "$created_at": now
            })
            tx.commit()
        
        pool.retry_operation_sync(create_firm_and_assign_owner)
        logging.info(f"Фирма {new_firm_id} и владелец {owner_user_id} успешно созданы/обновлены в firms-database.")
    
    except LogicError as e:
        return conflict(str(e))
    except Exception as e:
        logging.error(f"Ошибка при работе с firms-database: {e}", exc_info=True)
        return server_error(f"Failed to create firm record: {e}")

    logging.info(f"Фирма {new_firm_id} успешно создана. Дополнительные таблицы не требуются в текущей версии проекта.")

    return created({"message": "Firm created successfully", "firm_id": new_firm_id})
```