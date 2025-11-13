```python
import json
import os
import ydb
from utils import (
    parse_event, EventParseError,
    JsonLogger,
    now_utc,
    verify_password,
    issue_jwt,
    validate_phone_number,
    ok, bad_request, unauthorized, server_error
)
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env

def handler(event, context):
    logger = JsonLogger()
    logger.info("Refresh-token invoked")

    try:
        req = parse_event(event)
        body = req.get("body_dict") or {}
    except EventParseError as e:
        logger.warn("request.parse_error", error=str(e))
        return bad_request(f"Invalid request: {e}")

    email = (body.get("email") or "").strip().lower() if body.get("email") else None
    phone_number_raw = (body.get("phone_number") or "").strip() if body.get("phone_number") else None
    password = body.get("password")

    # Валидация и нормализация телефона
    phone_number = validate_phone_number(phone_number_raw) if phone_number_raw else None
    if phone_number_raw and not phone_number:
        logger.warn("request.invalid_phone", phone=phone_number_raw)
        return bad_request("Invalid phone number format.")

    # Проверка обязательных полей
    if not password:
        logger.warn("request.missing_password")
        return bad_request("Password is required.")
    
    if not email and not phone_number:
        logger.warn("request.missing_identifier")
        return bad_request("Either email or phone_number is required.")

    try:
        ydb_creds = ydb_creds_from_env()
        endpoint = os.environ.get("YDB_ENDPOINT")
        database = os.environ.get("YDB_DATABASE")
        if not endpoint or not database:
            raise RuntimeError("YDB_ENDPOINT or YDB_DATABASE not configured")
        pool = get_session_pool(endpoint, database, credentials=ydb_creds)
    except Exception as e:
        logger.error("db.connection_error", error=str(e))
        return server_error("Internal Server Error")

    def refresh_tx(session):
        tx = session.transaction(ydb.SerializableReadWrite())
        
        # Строим запрос для поиска по email или phone
        if email and phone_number:
            select_q = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8; DECLARE $phone AS Utf8;
                SELECT user_id, password_hash, is_active, email, phone_number
                FROM users WHERE email = $email OR phone_number = $phone LIMIT 1;
            """
            query_params = {"$email": email, "$phone": phone_number}
        elif email:
            select_q = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8;
                SELECT user_id, password_hash, is_active, email, phone_number
                FROM users WHERE email = $email;
            """
            query_params = {"$email": email}
        else:  # only phone
            select_q = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $phone AS Utf8;
                SELECT user_id, password_hash, is_active, email, phone_number
                FROM users WHERE phone_number = $phone;
            """
            query_params = {"$phone": phone_number}
        
        rs = tx.execute(session.prepare(select_q), query_params)
        if not rs[0].rows:
            tx.rollback()
            return {"status": 401}
        
        row = rs[0].rows[0]
        if not getattr(row, "is_active", False):
            tx.rollback()
            return {"status": 401}
        
        if not verify_password(password, row.password_hash):
            tx.rollback()
            return {"status": 401}

        user_id = row.user_id
        now = now_utc()
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            tx.rollback()
            raise RuntimeError("JWT_SECRET not configured")

        # Генерируем токен с email и/или phone в claims
        user_email = getattr(row, "email", None)
        user_phone = getattr(row, "phone_number", None)
        claims = {}
        if user_email:
            claims["email"] = user_email
        if user_phone:
            claims["phone_number"] = user_phone
        new_token = issue_jwt(user_id, secret=secret, claims=claims)

        update_q = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $user_id AS Utf8;
            DECLARE $now AS Timestamp;
            DECLARE $token AS Utf8;
            UPDATE users SET last_login_at = $now, jwt_token = $token WHERE user_id = $user_id;
        """
        tx.execute(session.prepare(update_q), {"$user_id": user_id, "$now": now, "$token": new_token})
        tx.commit()
        return {"token": new_token}

    try:
        result = pool.retry_operation_sync(refresh_tx)
    except Exception as e:
        logger.error("refresh.unexpected", error=str(e), exc_info=True)
        return server_error("Internal Server Error")

    if "token" in result:
        return ok({"token": result["token"]})

    return unauthorized("Invalid credentials.")
```