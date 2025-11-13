```python
import json
import os
import ydb
from custom_errors import NotFoundError, AuthError
from utils import hash_password, issue_jwt, ok, JsonLogger

def handle_reset(session, email: str = None, phone_number: str = None, new_password: str = None, current_password_hash: str = None):
    """
    Проверяет хеш текущего пароля, обновляет его и сессию (jwt_token), и возвращает новый JWT.
    """
    logger = JsonLogger()
    tx = session.transaction(ydb.SerializableReadWrite())

    # 1. Ищем активного пользователя по email или phone
    if email and phone_number:
        query_text = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $email AS Utf8; DECLARE $phone AS Utf8;
            SELECT user_id, password_hash, email, phone_number
            FROM users WHERE (email = $email OR phone_number = $phone) AND is_active = true LIMIT 1;
        """
        query_params = {'$email': email, '$phone': phone_number}
    elif email:
        query_text = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $email AS Utf8;
            SELECT user_id, password_hash, email, phone_number
            FROM users WHERE email = $email AND is_active = true;
        """
        query_params = {'$email': email}
    else:  # only phone
        query_text = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $phone AS Utf8;
            SELECT user_id, password_hash, email, phone_number
            FROM users WHERE phone_number = $phone AND is_active = true;
        """
        query_params = {'$phone': phone_number}
    
    result = tx.execute(session.prepare(query_text), query_params)

    if not result[0].rows:
        tx.rollback()
        raise NotFoundError("User with this email not found or is not active.")

    user_data = result[0].rows[0]
    db_password_hash = user_data.password_hash
    user_id = user_data.user_id

    # 2. Сверяем хеш из запроса с хешем из БД
    if current_password_hash != db_password_hash:
        tx.rollback()
        raise AuthError("Invalid current password hash provided.")

    # 3. Генерируем новый хеш пароля и новый токен с email и/или phone в claims
    new_hashed_password = hash_password(new_password)
    jwt_secret = os.environ.get('JWT_SECRET')
    if not jwt_secret:
        raise RuntimeError("JWT_SECRET not configured")
    
    user_email = getattr(user_data, "email", None)
    user_phone = getattr(user_data, "phone_number", None)
    claims = {}
    if user_email:
        claims["email"] = user_email
    if user_phone:
        claims["phone_number"] = user_phone
    new_token = issue_jwt(user_id, secret=jwt_secret, claims=claims)

    # 4. Атомарно обновляем пароль и токен в ОДНОМ запросе
    update_query_text = f"""
        PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
        DECLARE $user_id AS Utf8;
        DECLARE $new_hash AS Utf8;
        DECLARE $new_token AS Utf8;
        UPDATE users SET password_hash = $new_hash, jwt_token = $new_token WHERE user_id = $user_id;
    """
    tx.execute(session.prepare(update_query_text), {
        '$user_id': user_id,
        '$new_hash': new_hashed_password,
        '$new_token': new_token
    })
    
    tx.commit()

    logger.info("password_manager.reset_ok", email=user_email, phone=user_phone)
    return ok({"token": new_token})
```