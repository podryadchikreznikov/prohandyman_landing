# -*- coding: utf-8 -*-
import datetime
import traceback

import ydb

from utils import hash_password, now_utc, ok, not_found, server_error, json_response, send_sms_code

from common import CODE_EXPIRY_LOGIN_MINUTES, build_request_settings


def handle_reset_password(
    *,
    pool,
    database: str,
    table_name: str,
    phone_number: str,
    new_password: str,
    verification_code: str,
    auto_confirm_mode: bool,
    logger,
):
    def transaction(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())
        current_time = now_utc()
        request_settings = build_request_settings()

        select_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $phone AS Utf8;
            SELECT user_id, status
            FROM {table_name}
            WHERE phone_number = $phone;
        """
        select_stmt = session.prepare(select_q, settings=request_settings)
        rs = tx.execute(
            select_stmt,
            {"$phone": phone_number},
            settings=request_settings,
        )

        if not rs[0].rows:
            tx.rollback()
            return {"status": 404}

        row = rs[0].rows[0]
        user_id = row.user_id
        user_status = getattr(row, "status", "unverified")

        if user_status == "blocked":
            tx.rollback()
            return {"status": 423, "message": "Account is blocked."}

        hashed = hash_password(new_password)
        code_expires = current_time + datetime.timedelta(minutes=CODE_EXPIRY_LOGIN_MINUTES)

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
                jwt_token = NULL,
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
        return {"status": "code_sent"}

    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error(
            "auth_manager.reset_password.error",
            phone=phone_number,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 404:
        return not_found("User not found.")

    if result.get("status") == 423:
        return json_response(423, {"message": result.get("message")})

    if result.get("status") == "code_sent":
        if not auto_confirm_mode and not send_sms_code(phone_number, verification_code):
            return server_error("Failed to send SMS.")
        logger.info("auth_manager.reset_password.code_sent", phone=phone_number)
        return ok({"message": "Verification code sent. Confirm to complete password reset.", "phone_number": phone_number})

    return server_error("Unexpected error.")