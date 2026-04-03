# -*- coding: utf-8 -*-
import datetime
import traceback

import ydb

from utils import now_utc, ok, not_found, server_error, json_response, send_sms_code

from common import (
    CODE_EXPIRY_REGISTER_MINUTES,
    CODE_RESEND_MINUTES,
    build_request_settings,
    normalize_timestamp,
)


def handle_resend_code(
    *,
    pool,
    database: str,
    table_name: str,
    phone_number: str,
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
            SELECT user_id, verification_expires_at
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

        prev_expires = normalize_timestamp(getattr(row, "verification_expires_at", None))
        if prev_expires:
            created_at_est = prev_expires - datetime.timedelta(minutes=CODE_EXPIRY_REGISTER_MINUTES)
            resend_allowed = current_time - datetime.timedelta(minutes=CODE_RESEND_MINUTES)
            if created_at_est > resend_allowed:
                tx.rollback()
                return {"status": 429}

        code_expires = current_time + datetime.timedelta(minutes=CODE_EXPIRY_REGISTER_MINUTES)
        update_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $user_id AS Utf8;
            DECLARE $code AS Utf8;
            DECLARE $expires AS Timestamp;
            DECLARE $now AS Timestamp;
            UPDATE {table_name}
            SET verification_code = $code,
                verification_expires_at = $expires,
                updated_at = $now
            WHERE user_id = $user_id;
        """
        update_stmt = session.prepare(update_q, settings=request_settings)
        tx.execute(
            update_stmt,
            {"$user_id": user_id, "$code": verification_code, "$expires": code_expires, "$now": current_time},
            settings=request_settings,
        )
        tx.commit()
        return {"status": "code_sent"}

    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error(
            "auth_manager.resend_code.error",
            phone=phone_number,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 404:
        return not_found("User not found.")

    if result.get("status") == 429:
        return json_response(429, {"message": "Please wait before requesting a new code.", "phone_number": phone_number})

    if result.get("status") == "code_sent":
        if not auto_confirm_mode and not send_sms_code(phone_number, verification_code):
            return server_error("Failed to send SMS.")
        logger.info("auth_manager.resend_code.sent", phone=phone_number)
        return ok({"message": "Verification code sent.", "phone_number": phone_number})

    return server_error("Unexpected error.")