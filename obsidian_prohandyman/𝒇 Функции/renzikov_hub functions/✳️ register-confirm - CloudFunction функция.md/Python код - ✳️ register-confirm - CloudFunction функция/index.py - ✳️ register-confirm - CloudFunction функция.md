```python
import json
import os
import datetime
import ydb
from utils import (
    parse_event, EventParseError,
    issue_jwt,
    now_utc,
    JsonLogger,
    validate_phone_number,
    ok, bad_request, not_found, server_error
)
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env


def _normalize_timestamp(ts):
    if ts is None:
        return None
    if isinstance(ts, (int, float)):  # микросекунды
        return datetime.datetime.fromtimestamp(ts / 1_000_000, tz=datetime.timezone.utc)
    if isinstance(ts, datetime.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=datetime.timezone.utc)
    return None


def handler(event, context):
    logger = JsonLogger()
    
    try:
        req = parse_event(event)
        data = req.get("body_dict") or {}
    except EventParseError as e:
        logger.error("request.parse_error", error=str(e))
        return bad_request(str(e))
        
    email = (data.get('email') or '').strip().lower() if data.get('email') else None
    phone_number_raw = (data.get('phone_number') or '').strip() if data.get('phone_number') else None
    code = data.get('code')

    # Валидация и нормализация телефона
    phone_number = validate_phone_number(phone_number_raw) if phone_number_raw else None
    if phone_number_raw and not phone_number:
        logger.warn("request.invalid_phone", phone=phone_number_raw)
        return bad_request("Invalid phone number format.")

    # Проверка обязательных полей
    if not code:
        logger.warn("request.missing_code")
        return bad_request("Code is required.")
    
    if not email and not phone_number:
        logger.warn("request.missing_identifier")
        return bad_request("Either email or phone_number is required.")

    # Креды из ENV
    try:
        ydb_creds = ydb_creds_from_env()

        auth_endpoint = os.environ.get("YDB_ENDPOINT")
        auth_database = os.environ.get("YDB_DATABASE")
        firms_endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        firms_database = os.environ.get("YDB_DATABASE_FIRMS")
        
        if not all([auth_endpoint, auth_database, firms_endpoint, firms_database]):
            raise RuntimeError("YDB endpoints or databases not configured")

        # Пулы сессий
        auth_pool = get_session_pool(auth_endpoint, auth_database, credentials=ydb_creds)
        firms_pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)
    except Exception as e:
        logger.error("db.connection_error", error=str(e))
        return server_error("Internal Server Error")

    def transaction(session):
        # Эта транзакция работает с jwt-database
        tx = session.transaction(ydb.SerializableReadWrite())

        # 1. Ищем неактивного пользователя в jwt-database по email или phone
        if email and phone_number:
            select_query = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8; DECLARE $phone AS Utf8;
                SELECT user_id, verification_code, code_expires_at, email, phone_number
                FROM users WHERE (email = $email OR phone_number = $phone) AND is_active = false
                LIMIT 1;
            """
            query_params = {'$email': email, '$phone': phone_number}
        elif email:
            select_query = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}'); DECLARE $email AS Utf8;
                SELECT user_id, verification_code, code_expires_at, email, phone_number
                FROM users WHERE email = $email AND is_active = false;
            """
            query_params = {'$email': email}
        else:  # only phone
            select_query = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}'); DECLARE $phone AS Utf8;
                SELECT user_id, verification_code, code_expires_at, email, phone_number
                FROM users WHERE phone_number = $phone AND is_active = false;
            """
            query_params = {'$phone': phone_number}
        
        result_sets = tx.execute(session.prepare(select_query), query_params)
        
        if not result_sets[0].rows:
            tx.rollback()
            return {"status": 404, "message": "User not found or already active."}

        user_data = result_sets[0].rows[0]
        
        # 2. Проверяем код и срок его жизни
        expires_dt = _normalize_timestamp(user_data.code_expires_at)
        is_expired = expires_dt is not None and now_utc() > expires_dt

        if user_data.verification_code != code or is_expired:
            tx.rollback()
            return {"status": 400, "message": "Invalid or expired code."}

        # 3. Активируем пользователя в jwt-database
        user_id_to_activate = user_data.user_id
        update_query = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}'); DECLARE $user_id AS Utf8;
            UPDATE users SET is_active = true, verification_code = NULL, code_expires_at = NULL WHERE user_id = $user_id;
        """
        tx.execute(session.prepare(update_query), {'$user_id': user_id_to_activate})
        tx.commit() # Коммитим изменения в jwt-database

        # 4. Обновляем user_id в ожидающих приглашениях в firms-database (отдельная операция)
        def update_invitations_in_firms(firm_session):
            logger.info("confirm.searching_invitations", email=email)
            update_tx = firm_session.transaction(ydb.SerializableReadWrite())
            update_query_text = """
                DECLARE $new_user_id AS Utf8; DECLARE $email AS Utf8;
                UPDATE Users SET user_id = $new_user_id
                WHERE email = $email AND is_active = false;
            """
            update_tx.execute(
                firm_session.prepare(update_query_text),
                {'$new_user_id': user_id_to_activate, '$email': email}
            )
            update_tx.commit()
            logger.info("confirm.invitations_updated", email=email, user_id=user_id_to_activate)

        try:
            firms_pool.retry_operation_sync(update_invitations_in_firms)
        except Exception as e:
            # Если здесь произойдет ошибка, пользователь уже активирован, но не привязан к фирме.
            # Это критическая ситуация, которую нужно залогировать.
            logger.error("confirm.invitations_link_failed", user_id=user_id_to_activate, email=email, error=str(e))
            # Возвращаем токен, так как основная регистрация прошла успешно. Проблему с приглашением придется решать вручную.
        
        # 5. Генерируем токен с email и/или phone в claims
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
        
        token = issue_jwt(user_id_to_activate, secret=jwt_secret, claims=claims)
        return {"status": 200, "token": token}

    try:
        result = auth_pool.retry_operation_sync(transaction)
        if result.get("status") == 200:
            logger.info("confirm.success", email=email)
            return ok({"token": result["token"]})
        elif result.get("status") == 404:
            logger.warn("confirm.user_not_found", email=email)
            return not_found(result.get("message"))
        else:
            logger.warn("confirm.invalid_code", email=email)
            return bad_request(result.get("message"))
    except Exception as e:
        logger.error("confirm.unexpected_error", email=email, error=str(e))
        return server_error("Internal Server Error")
```