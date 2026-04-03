# -*- coding: utf-8 -*-
import datetime
import traceback

import ydb

from utils import (
    verify_password,
    issue_jwt,
    now_utc,
    ok,
    unauthorized,
    server_error,
    json_response,
    send_sms_code,
)

from common import CODE_EXPIRY_LOGIN_MINUTES, build_request_settings


def handle_login(
    *,
    pool,
    database: str,
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
            SELECT user_id, password_hash, status, jwt_token
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
            return {"status": 401, "message": "Invalid credentials."}

        row = rs[0].rows[0]
        user_status = getattr(row, "status", "unverified")

        if user_status == "blocked":
            tx.rollback()
            return {"status": 423, "message": "Account is blocked."}

        if user_status == "unverified":
            tx.rollback()
            return {"status": 423, "message": "Account not verified."}

        if not verify_password(password, row.password_hash):
            tx.rollback()
            return {"status": 401, "message": "Invalid credentials."}

        user_id = row.user_id

        if auto_confirm_mode:
            stored_token = getattr(row, "jwt_token", None)
            if stored_token:
                update_q = f"""
                    PRAGMA TablePathPrefix('{database}');
                    DECLARE $user_id AS Utf8;
                    DECLARE $now AS Timestamp;
                    UPDATE {table_name}
                    SET last_login_at = $now, updated_at = $now
                    WHERE user_id = $user_id;
                """
                update_stmt = session.prepare(update_q, settings=request_settings)
                tx.execute(
                    update_stmt,
                    {"$user_id": user_id, "$now": current_time},
                    settings=request_settings,
                )
                tx.commit()
                return {"status": 200, "token": stored_token}

            token = issue_jwt(user_id, secret=jwt_secret, claims={"phone_number": phone_number})
            update_q = f"""
                PRAGMA TablePathPrefix('{database}');
                DECLARE $user_id AS Utf8;
                DECLARE $token AS Utf8;
                DECLARE $now AS Timestamp;
                UPDATE {table_name}
                SET jwt_token = $token, last_login_at = $now, updated_at = $now
                WHERE user_id = $user_id;
            """
            update_stmt = session.prepare(update_q, settings=request_settings)
            tx.execute(
                update_stmt,
                {"$user_id": user_id, "$token": token, "$now": current_time},
                settings=request_settings,
            )
            tx.commit()
            return {"status": 200, "token": token}

        code_expires = current_time + datetime.timedelta(minutes=CODE_EXPIRY_LOGIN_MINUTES)
        update_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $user_id AS Utf8;
            DECLARE $code AS Utf8;
            DECLARE $expires AS Timestamp;
            DECLARE $now AS Timestamp;
            UPDATE {table_name}
            SET verification_code = $code, verification_expires_at = $expires, updated_at = $now
            WHERE user_id = $user_id;
        """
        update_stmt = session.prepare(update_q, settings=request_settings)
        tx.execute(
            update_stmt,
            {
                "$user_id": user_id,
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
            "auth_manager.login.error",
            phone=phone_number,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 200 and result.get("token"):
        logger.info("auth_manager.login.auto_confirm_success", phone=phone_number)
        return ok({"token": result["token"]})

    if result.get("status") == "code_sent":
        if not send_sms_code(phone_number, verification_code):
            return server_error("Failed to send SMS.")
        logger.info("auth_manager.login.code_sent", phone=phone_number)
        return ok({"message": "Verification code sent.", "phone_number": phone_number})

    status = result.get("status")
    if status == 401:
        return unauthorized(result.get("message"))
    if status == 423:
        return json_response(423, {"message": result.get("message")})

    return server_error("Unexpected error.")