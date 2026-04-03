# -*- coding: utf-8 -*-
import datetime
import traceback
import uuid

import ydb

from utils import (
    hash_password,
    issue_jwt,
    now_utc,
    ok,
    conflict,
    server_error,
    send_sms_code,
)

from common import (
    CODE_EXPIRY_REGISTER_MINUTES,
    CODE_RESEND_MINUTES,
    build_request_settings,
    normalize_timestamp,
)


def _ensure_aggregate_state_table(pool: ydb.SessionPool, database: str, user_id: str, logger) -> None:
    table_name = f"aggregate_state_{user_id}"

    def _op(session: ydb.Session):
        q = f"""
            PRAGMA TablePathPrefix('{database}');
            CREATE TABLE IF NOT EXISTS `{table_name}` (
                entity_type Utf8,
                entity_id Utf8,
                event_type Utf8,
                schema_version Int32,
                state_json Json,
                created_at Timestamp,
                updated_at Timestamp,
                PRIMARY KEY (entity_type, entity_id)
            );
        """
        session.execute_scheme(q)

    pool.retry_operation_sync(_op)
    logger.info("auth_manager.meta.aggregate_state_table_ready", table=table_name)


def handle_register(
    *,
    pool,
    database: str,
    meta_pool,
    meta_database: str,
    table_name: str,
    phone_number: str,
    password: str,
    verification_code: str,
    auto_confirm_mode: bool,
    jwt_secret: str,
    logger,
):
    def transaction(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())
        current_time = now_utc()
        request_settings = build_request_settings()

        select_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $phone AS Utf8;
            SELECT user_id, status, verification_expires_at
            FROM {table_name}
            WHERE phone_number = $phone;
        """
        select_stmt = session.prepare(select_q, settings=request_settings)
        rs = tx.execute(
            select_stmt,
            {"$phone": phone_number},
            settings=request_settings,
        )

        if rs[0].rows:
            row = rs[0].rows[0]
            user_status = getattr(row, "status", "unverified")

            if user_status == "active":
                tx.rollback()
                return {"status": 409, "message": "User already exists.", "user_id": row.user_id}

            user_id = row.user_id
            prev_expires = normalize_timestamp(getattr(row, "verification_expires_at", None))
            if prev_expires:
                created_at_est = prev_expires - datetime.timedelta(minutes=CODE_EXPIRY_REGISTER_MINUTES)
                resend_allowed = current_time - datetime.timedelta(minutes=CODE_RESEND_MINUTES)
                if created_at_est > resend_allowed:
                    tx.rollback()
                    return {"status": "already_sent", "user_id": user_id}

            hashed = hash_password(password)
            code_expires = current_time + datetime.timedelta(minutes=CODE_EXPIRY_REGISTER_MINUTES)

            update_q = f"""
                PRAGMA TablePathPrefix('{database}');
                DECLARE $user_id AS Utf8;
                DECLARE $password_hash AS Utf8;
                DECLARE $code AS Utf8;
                DECLARE $expires AS Timestamp;
                DECLARE $now AS Timestamp;
                UPDATE {table_name}
                SET password_hash = $password_hash,
                    verification_code = $code,
                    verification_expires_at = $expires,
                    updated_at = $now
                WHERE user_id = $user_id;
            """
            update_stmt = session.prepare(update_q, settings=request_settings)
            tx.execute(
                update_stmt,
                {
                    "$user_id": user_id,
                    "$password_hash": hashed,
                    "$code": verification_code,
                    "$expires": code_expires,
                    "$now": current_time,
                },
                settings=request_settings,
            )
            tx.commit()
            return {"status": "code_sent", "user_id": user_id}

        new_user_id = str(uuid.uuid4())
        hashed = hash_password(password)

        if auto_confirm_mode:
            token = issue_jwt(new_user_id, secret=jwt_secret, claims={"phone_number": phone_number})
            insert_q = f"""
                PRAGMA TablePathPrefix('{database}');
                DECLARE $user_id AS Utf8;
                DECLARE $phone AS Utf8;
                DECLARE $password_hash AS Utf8;
                DECLARE $token AS Utf8;
                DECLARE $now AS Timestamp;
                UPSERT INTO {table_name}
                    (user_id, phone_number, password_hash, jwt_token, status, last_login_at, created_at, updated_at)
                VALUES ($user_id, $phone, $password_hash, $token, 'active', $now, $now, $now);
            """
            insert_stmt = session.prepare(insert_q, settings=request_settings)
            tx.execute(
                insert_stmt,
                {
                    "$user_id": new_user_id,
                    "$phone": phone_number,
                    "$password_hash": hashed,
                    "$token": token,
                    "$now": current_time,
                },
                settings=request_settings,
            )
            tx.commit()
            return {"status": 200, "token": token, "user_id": new_user_id}

        code_expires = current_time + datetime.timedelta(minutes=CODE_EXPIRY_REGISTER_MINUTES)
        insert_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $user_id AS Utf8;
            DECLARE $phone AS Utf8;
            DECLARE $password_hash AS Utf8;
            DECLARE $code AS Utf8;
            DECLARE $expires AS Timestamp;
            DECLARE $now AS Timestamp;
            UPSERT INTO {table_name}
                (user_id, phone_number, password_hash, verification_code, verification_expires_at, status, created_at, updated_at)
            VALUES ($user_id, $phone, $password_hash, $code, $expires, 'unverified', $now, $now);
        """
        insert_stmt = session.prepare(insert_q, settings=request_settings)
        tx.execute(
            insert_stmt,
            {
                "$user_id": new_user_id,
                "$phone": phone_number,
                "$password_hash": hashed,
                "$code": verification_code,
                "$expires": code_expires,
                "$now": current_time,
            },
            settings=request_settings,
        )
        tx.commit()
        return {"status": "code_sent", "user_id": new_user_id}

    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error(
            "auth_manager.register.error",
            phone=phone_number,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    # Идемпотентно создаем aggregate_state_{user_id} в metadata-system
    # (делаем вне транзакции users/dispatchers, чтобы не смешивать БД)
    try:
        if isinstance(result, dict) and isinstance(result.get("user_id"), str) and result.get("user_id"):
            _ensure_aggregate_state_table(meta_pool, meta_database, result["user_id"], logger)
    except Exception as e:
        logger.error(
            "auth_manager.meta.aggregate_state_table_error",
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 200 and result.get("token"):
        logger.info("auth_manager.register.auto_confirm_success", phone=phone_number)
        return ok({"token": result["token"]})

    if result.get("status") == "code_sent":
        if not send_sms_code(phone_number, verification_code):
            return server_error("Failed to send SMS.")
        logger.info("auth_manager.register.code_sent", phone=phone_number)
        return ok({"message": "Verification code sent.", "phone_number": phone_number})

    if result.get("status") == "already_sent":
        return ok({"message": "Verification code already sent. Please wait.", "phone_number": phone_number})

    if result.get("status") == 409:
        return conflict(result.get("message"))

    return server_error("Unexpected error.")