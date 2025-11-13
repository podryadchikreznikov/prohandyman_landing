```python
# -*- coding: utf-8 -*-
import json
import os
import uuid
import random
import datetime
import traceback
import ydb

from utils import (
    parse_event, EventParseError,
    hash_password,
    issue_jwt,
    now_utc,
    JsonLogger,
    ok, created, bad_request, conflict, server_error, json_response,
    validate_phone_number, send_sms_code
)
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env

try:
    from utils import email_utils
except ImportError:
    email_utils = None


def _normalize_timestamp(ts):
    """YDB может вернуть timestamp как int (микросекунды) или datetime."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):  # микросекунды
        return datetime.datetime.fromtimestamp(ts / 1_000_000, tz=datetime.timezone.utc)
    if isinstance(ts, datetime.datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=datetime.timezone.utc)
    return None


def handler(event, context):
    logger = JsonLogger()
    logger.info("register.invocation")

    email = None  # чтобы не потерять в логе при исключениях
    auto_confirm_mode = os.environ.get('AUTO_CONFIRM_MODE', 'false').lower() == 'true'

    # 1) Парсинг входных данных
    try:
        req = parse_event(event)
        data = req.get("body_dict") or {}
    except EventParseError as e:
        logger.error("request.parse_error", error=str(e))
        return bad_request(str(e))

    email = (data.get('email') or '').strip().lower() if data.get('email') else None
    phone_number_raw = (data.get('phone_number') or '').strip() if data.get('phone_number') else None
    password = data.get('password')
    user_name = data.get('user_name')
    verification_method = (data.get('verification_method') or '').lower()

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
    
    # Определение канала отправки кода
    if not verification_method:
        verification_method = 'email' if email else 'sms'
    elif verification_method not in ['email', 'sms']:
        logger.warn("request.invalid_verification_method", method=verification_method)
        return bad_request("verification_method must be 'email' or 'sms'.")
    
    # Проверка что выбранный канал доступен
    if verification_method == 'email' and not email:
        logger.warn("request.email_required_for_email_verification")
        return bad_request("Email is required when verification_method is 'email'.")
    if verification_method == 'sms' and not phone_number:
        logger.warn("request.phone_required_for_sms_verification")
        return bad_request("Phone number is required when verification_method is 'sms'.")

    # 2) Получаем креды и создаём пулы сессий
    try:
        ydb_creds = ydb_creds_from_env()

        auth_endpoint = os.environ.get("YDB_ENDPOINT")
        auth_database = os.environ.get("YDB_DATABASE")
        firms_endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        firms_database = os.environ.get("YDB_DATABASE_FIRMS")

        if not all([auth_endpoint, auth_database, firms_endpoint, firms_database]):
            raise RuntimeError("YDB endpoints or databases not configured")

        auth_pool = get_session_pool(auth_endpoint, auth_database, credentials=ydb_creds)
        firms_pool = get_session_pool(firms_endpoint, firms_database, credentials=ydb_creds)
    except Exception as e:
        error_details = {"error_type": type(e).__name__, "error": str(e), "trace": traceback.format_exc()}
        logger.error("db.connection_error", **error_details)
        print(f"DB CONNECTION ERROR in register-request: {json.dumps(error_details, ensure_ascii=False, default=str)}")
        return server_error("Internal Server Error")

    # 3) Главная транзакция (только jwt-database)
    def transaction(session):
        tx = session.transaction(ydb.SerializableReadWrite())
        current_time = now_utc()

        # 3.1) Проверяем существование пользователя по email и/или phone_number
        # Строим запрос динамически в зависимости от наличия email/phone
        if email and phone_number:
            check_query = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8;
                DECLARE $phone AS Utf8;
                SELECT user_id, is_active, code_expires_at, email, phone_number
                FROM users
                WHERE email = $email OR phone_number = $phone;
            """
            query_params = {'$email': email, '$phone': phone_number}
        elif email:
            check_query = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $email AS Utf8;
                SELECT user_id, is_active, code_expires_at, email, phone_number
                FROM users
                WHERE email = $email;
            """
            query_params = {'$email': email}
        else:  # only phone_number
            check_query = f"""
                PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                DECLARE $phone AS Utf8;
                SELECT user_id, is_active, code_expires_at, email, phone_number
                FROM users
                WHERE phone_number = $phone;
            """
            query_params = {'$phone': phone_number}
        
        result_sets = tx.execute(session.prepare(check_query), query_params)

        if result_sets[0].rows:
            existing_row = result_sets[0].rows[0]

            # Случай: активный пользователь уже есть
            if getattr(existing_row, "is_active", False):
                tx.rollback()
                return {"status": 409, "message": "User with this email already exists."}

            # Случай: неактивен — можно ли переслать новый код?
            prev_expires = _normalize_timestamp(getattr(existing_row, "code_expires_at", None))
            # создавался ~ за 10 минут до expires
            created_at_est = (prev_expires - datetime.timedelta(minutes=10)) if prev_expires else (current_time - datetime.timedelta(minutes=10))
            three_minutes_ago = current_time - datetime.timedelta(minutes=3)

            if created_at_est <= three_minutes_ago:
                new_code = str(random.randint(100000, 999999))
                new_expires = current_time + datetime.timedelta(minutes=10)

                # Обновляем код используя user_id (более надежно чем email/phone)
                existing_user_id = getattr(existing_row, "user_id")
                update_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $code AS Utf8; DECLARE $expires AS Timestamp;
                    UPDATE users
                    SET verification_code = $code, code_expires_at = $expires
                    WHERE user_id = $user_id AND is_active = false;
                """
                tx.execute(session.prepare(update_query), {
                    '$user_id': existing_user_id, '$code': new_code, '$expires': new_expires
                })
                tx.commit()

                # Отправляем код через выбранный канал (вне транзакции)
                if not auto_confirm_mode:
                    if verification_method == 'email':
                        code_sent = email_utils.send_verification_code(email, new_code) if email_utils else False
                        if not code_sent:
                            logger.error("email.send_failed", email=email, action="update")
                            return {"status": 500, "message": "Failed to send verification code."}
                    else:  # sms
                        code_sent = send_sms_code(phone_number, new_code)
                        if not code_sent:
                            logger.error("sms.send_failed", phone=phone_number, action="update")
                            return {"status": 500, "message": "Failed to send verification code."}

                return {"status": 200, "message": "Verification code sent."}
            else:
                tx.rollback()
                return {"status": 200, "message": "Verification code already sent. Please check your email."}

        # 3.2) Новый пользователь — требуем user_name
        if not user_name:
            tx.rollback()
            return {"status": 400, "message": "user_name is required for new account."}

        # 3.3) Пытаемся переиспользовать user_id из приглашения (firms-database)
        # Ищем по email если он указан
        def check_pending_invitation(firm_session):
            if not email:  # Если только телефон, пропускаем проверку приглашений
                return None
            ro_tx = firm_session.transaction(ydb.OnlineReadOnly())
            check_query = """
                DECLARE $email AS Utf8;
                SELECT user_id
                FROM Users
                WHERE email = $email AND is_active = false
                LIMIT 1;
            """
            res = ro_tx.execute(firm_session.prepare(check_query), {'$email': email})
            ro_tx.commit()
            return res[0].rows[0].user_id if res[0].rows else None

        try:
            existing_invitation_user_id = firms_pool.retry_operation_sync(check_pending_invitation)
        except Exception as e:
            logger.warn("register.invitation_check_failed", email=email, phone=phone_number, error=str(e))
            existing_invitation_user_id = None

        new_user_id = existing_invitation_user_id or str(uuid.uuid4())
        hashed_password = hash_password(password)
        logger.info("register.creating_user", user_id=new_user_id, email=email, from_invitation=existing_invitation_user_id is not None)

        if auto_confirm_mode:
            # 3.4) Тестовый режим AUTO_CONFIRM: сразу активируем и выдаём токен
            if email and phone_number:
                upsert_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $email AS Utf8; DECLARE $phone AS Utf8;
                    DECLARE $password_hash AS Utf8; DECLARE $user_name AS Utf8;
                    DECLARE $created_at AS Timestamp;
                    UPSERT INTO users (user_id, email, phone_number, password_hash, user_name, created_at, is_active)
                    VALUES ($user_id, $email, $phone, $password_hash, $user_name, $created_at, true);
                """
                query_params = {
                    '$user_id': new_user_id, '$email': email, '$phone': phone_number,
                    '$password_hash': hashed_password, '$user_name': user_name, '$created_at': current_time
                }
            elif email:
                upsert_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $email AS Utf8;
                    DECLARE $password_hash AS Utf8; DECLARE $user_name AS Utf8;
                    DECLARE $created_at AS Timestamp;
                    UPSERT INTO users (user_id, email, password_hash, user_name, created_at, is_active)
                    VALUES ($user_id, $email, $password_hash, $user_name, $created_at, true);
                """
                query_params = {
                    '$user_id': new_user_id, '$email': email,
                    '$password_hash': hashed_password, '$user_name': user_name, '$created_at': current_time
                }
            else:  # only phone
                upsert_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $phone AS Utf8;
                    DECLARE $password_hash AS Utf8; DECLARE $user_name AS Utf8;
                    DECLARE $created_at AS Timestamp;
                    UPSERT INTO users (user_id, phone_number, password_hash, user_name, created_at, is_active)
                    VALUES ($user_id, $phone, $password_hash, $user_name, $created_at, true);
                """
                query_params = {
                    '$user_id': new_user_id, '$phone': phone_number,
                    '$password_hash': hashed_password, '$user_name': user_name, '$created_at': current_time
                }
            
            tx.execute(session.prepare(upsert_query), query_params)

            # ВАЖНО: НЕ трогаем firms.Users — не пытаемся обновлять PK (user_id)!
            # См. YDB docs: UPDATE can't change primary key columns.

            jwt_secret = os.environ.get('JWT_SECRET')
            if not jwt_secret:
                raise RuntimeError("JWT_SECRET not configured")

            # Создаем JWT с email и/или phone в claims
            claims = {}
            if email:
                claims["email"] = email
            if phone_number:
                claims["phone_number"] = phone_number
            token = issue_jwt(new_user_id, secret=jwt_secret, claims=claims)
            tx.commit()
            return {"status": 201, "token": token}

        else:
            # 3.5) Стандартный режим: создаём неактивного пользователя с кодом
            code = str(random.randint(100000, 999999))
            expires = current_time + datetime.timedelta(minutes=10)

            # Создаем запрос в зависимости от наличия email/phone
            if email and phone_number:
                upsert_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $email AS Utf8; DECLARE $phone AS Utf8;
                    DECLARE $password_hash AS Utf8; DECLARE $user_name AS Utf8;
                    DECLARE $created_at AS Timestamp; DECLARE $code AS Utf8; DECLARE $expires AS Timestamp;
                    UPSERT INTO users (user_id, email, phone_number, password_hash, user_name, created_at, verification_code, code_expires_at, is_active)
                    VALUES ($user_id, $email, $phone, $password_hash, $user_name, $created_at, $code, $expires, false);
                """
                query_params = {
                    '$user_id': new_user_id, '$email': email, '$phone': phone_number,
                    '$password_hash': hashed_password, '$user_name': user_name,
                    '$created_at': current_time, '$code': code, '$expires': expires
                }
            elif email:
                upsert_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $email AS Utf8;
                    DECLARE $password_hash AS Utf8; DECLARE $user_name AS Utf8;
                    DECLARE $created_at AS Timestamp; DECLARE $code AS Utf8; DECLARE $expires AS Timestamp;
                    UPSERT INTO users (user_id, email, password_hash, user_name, created_at, verification_code, code_expires_at, is_active)
                    VALUES ($user_id, $email, $password_hash, $user_name, $created_at, $code, $expires, false);
                """
                query_params = {
                    '$user_id': new_user_id, '$email': email,
                    '$password_hash': hashed_password, '$user_name': user_name,
                    '$created_at': current_time, '$code': code, '$expires': expires
                }
            else:  # only phone
                upsert_query = f"""
                    PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
                    DECLARE $user_id AS Utf8; DECLARE $phone AS Utf8;
                    DECLARE $password_hash AS Utf8; DECLARE $user_name AS Utf8;
                    DECLARE $created_at AS Timestamp; DECLARE $code AS Utf8; DECLARE $expires AS Timestamp;
                    UPSERT INTO users (user_id, phone_number, password_hash, user_name, created_at, verification_code, code_expires_at, is_active)
                    VALUES ($user_id, $phone, $password_hash, $user_name, $created_at, $code, $expires, false);
                """
                query_params = {
                    '$user_id': new_user_id, '$phone': phone_number,
                    '$password_hash': hashed_password, '$user_name': user_name,
                    '$created_at': current_time, '$code': code, '$expires': expires
                }

            tx.execute(session.prepare(upsert_query), query_params)
            tx.commit()

            # Отправка кода через выбранный канал
            if verification_method == 'email':
                code_sent = email_utils.send_verification_code(email, code) if email_utils else False
                if not code_sent:
                    logger.error("email.send_failed", email=email, action="create")
                    return {"status": 500, "message": "Failed to send verification code."}
            else:  # sms
                code_sent = send_sms_code(phone_number, code)
                if not code_sent:
                    logger.error("sms.send_failed", phone=phone_number, action="create")
                    return {"status": 500, "message": "Failed to send verification code."}

            return {"status": 200, "message": "Verification code sent."}

    # 4) Оборачиваем транзакцию retry-обработчиком
    try:
        result = auth_pool.retry_operation_sync(transaction)

        if result.get("status") == 201:
            logger.info("register.success_auto_confirm", email=email)
            return created({"token": result["token"]})
        elif result.get("status") == 200:
            logger.info("register.code_sent", email=email)
            return ok({"message": result["message"]})
        elif result.get("status") == 409:
            logger.warn("register.user_exists", email=email)
            return conflict(result.get("message"))
        elif result.get("status") == 400:
            logger.warn("register.bad_request", email=email)
            return bad_request(result.get("message"))
        elif result.get("status") == 500:
            logger.error("register.internal_error", email=email)
            return server_error(result.get("message", "Internal Server Error"))
        else:
            return json_response(result.get("status", 500), {"message": result.get("message", "Internal Server Error")})
    except Exception as e:
        error_details = {
            "email": email,
            "error_type": type(e).__name__,
            "error": str(e),
            "trace": traceback.format_exc()
        }
        logger.error("register.critical_error", **error_details)
        print(f"CRITICAL ERROR in register-request: {json.dumps(error_details, ensure_ascii=False, default=str)}")
        return server_error("Internal Server Error")
```