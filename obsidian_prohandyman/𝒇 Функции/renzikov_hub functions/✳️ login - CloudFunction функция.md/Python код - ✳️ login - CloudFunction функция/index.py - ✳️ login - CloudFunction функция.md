

```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import traceback
import ydb

from utils import (
    parse_event, EventParseError,
    JsonLogger,
    now_utc,
    verify_password,
    issue_jwt,
    verify_jwt,
    validate_phone_number,
    ok, bad_request, unauthorized, server_error, json_response
)
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env

logger = JsonLogger()

def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        logger.error("config.env_missing", env=name)
        raise RuntimeError(f"{name} not configured")
    return val

def handler(event, context):
    logger.info("login.invoked")

    # 1) Парсинг входа
    try:
        req = parse_event(event)
        body = req.get("body_dict") or {}
    except EventParseError as e:
        logger.error("login.parse_error", error=str(e))
        return bad_request(f"Invalid request: {e}")

    email = (body.get("email") or "").strip().lower() if body.get("email") else None
    phone_number_raw = (body.get("phone_number") or "").strip() if body.get("phone_number") else None
    password = body.get("password")

    # Валидация и нормализация телефона
    phone_number = validate_phone_number(phone_number_raw) if phone_number_raw else None
    if phone_number_raw and not phone_number:
        logger.warn("login.invalid_phone", phone=phone_number_raw)
        return bad_request("Invalid phone number format.")

    # Проверка обязательных полей
    if not password:
        logger.warn("login.missing_password")
        return bad_request("Password is required.")
    
    if not email and not phone_number:
        logger.warn("login.missing_identifier")
        return bad_request("Either email or phone_number is required.")

    # 2) Конфигурация + YDB
    try:
        ydb_creds = ydb_creds_from_env()
        endpoint = _require_env("YDB_ENDPOINT")
        database = _require_env("YDB_DATABASE")
        pool = get_session_pool(endpoint, database, credentials=ydb_creds)
    except Exception as e:
        logger.error("login.db_connect_error", email=email, error=str(e))
        return server_error("Internal Server Error")

    # 3) Транзакция логина
    def transaction(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())
        jwt_secret = _require_env("JWT_SECRET")

        # Строим запрос для поиска по email или phone
        if email and phone_number:
            select_q = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8;
                DECLARE $phone AS Utf8;
                SELECT user_id, password_hash, is_active, jwt_token, email, phone_number
                FROM users
                WHERE email = $email OR phone_number = $phone
                LIMIT 1;
            """
            query_params = {"$email": email, "$phone": phone_number}
        elif email:
            select_q = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8;
                SELECT user_id, password_hash, is_active, jwt_token, email, phone_number
                FROM users
                WHERE email = $email;
            """
            query_params = {"$email": email}
        else:  # only phone
            select_q = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $phone AS Utf8;
                SELECT user_id, password_hash, is_active, jwt_token, email, phone_number
                FROM users
                WHERE phone_number = $phone;
            """
            query_params = {"$phone": phone_number}
        
        rs = tx.execute(session.prepare(select_q), query_params)

        if not rs[0].rows:
            tx.rollback()
            return {"status": 401}

        row = rs[0].rows[0]

        if not getattr(row, "is_active", False):
            tx.rollback()
            return {"status": 423}

        if not verify_password(password, row.password_hash):
            tx.rollback()
            return {"status": 401}

        now = now_utc()
        user_id = row.user_id
        
        # Проверяем существующий токен
        existing_token = getattr(row, "jwt_token", None)
        if existing_token:
            try:
                verify_jwt(existing_token, secret=jwt_secret, verify_exp=True)
                
                # Токен валиден, обновляем только last_login_at и возвращаем его
                update_q = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $now AS Timestamp;
                    UPDATE users SET last_login_at = $now WHERE user_id = $user_id;
                """
                tx.execute(session.prepare(update_q), {"$user_id": user_id, "$now": now})
                tx.commit()
                return {"token": existing_token}
            except Exception:
                logger.warn("login.existing_token_invalid", email=email)
                pass
        
        # Генерируем и сохраняем новый токен с email и/или phone в claims
        user_email = getattr(row, "email", None)
        user_phone = getattr(row, "phone_number", None)
        claims = {}
        if user_email:
            claims["email"] = user_email
        if user_phone:
            claims["phone_number"] = user_phone
        new_token = issue_jwt(user_id, secret=jwt_secret, claims=claims)
        update_q_with_token = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $user_id AS Utf8; DECLARE $now AS Timestamp; DECLARE $token AS Utf8;
            UPDATE users SET last_login_at = $now, jwt_token = $token WHERE user_id = $user_id;
        """
        tx.execute(session.prepare(update_q_with_token), {"$user_id": user_id, "$now": now, "$token": new_token})
        tx.commit()
        return {"token": new_token}

    # 4) Выполнение
    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error("login.unexpected_exception", email=email, error=str(e), trace=traceback.format_exc())
        return server_error("Internal Server Error")

    if "token" in result:
        logger.info("login.success", email=email)
        return ok({"token": result["token"]})

    status = result.get("status")
    if status == 423:
        logger.warn("login.not_confirmed", email=email, phone=phone_number)
        return json_response(423, {"message": "Account not confirmed. Please verify your email or phone number."})
    
    logger.warn("login.invalid_credentials", email=email)
    return unauthorized("Invalid credentials.")
```

