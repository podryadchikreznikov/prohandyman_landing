# -*- coding: utf-8 -*-
import traceback

import ydb

from utils import verify_password, now_utc, ok, not_found, unauthorized, server_error, json_response
from common import build_request_settings


def handle_reset_sessions(*, pool, database: str, table_name: str, phone_number: str, password: str, logger):
    def transaction(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())
        current_time = now_utc()
        request_settings = build_request_settings()

        select_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $phone AS Utf8;
            SELECT user_id, password_hash, status
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
        user_status = getattr(row, "status", "unverified")

        if user_status == "blocked":
            tx.rollback()
            return {"status": 423, "message": "Account is blocked."}

        if not verify_password(password, row.password_hash):
            tx.rollback()
            return {"status": 401, "message": "Invalid credentials."}

        user_id = row.user_id

        update_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $user_id AS Utf8;
            DECLARE $now AS Timestamp;
            UPDATE {table_name}
            SET jwt_token = NULL,
                updated_at = $now
            WHERE user_id = $user_id;
        """
        update_stmt = session.prepare(update_q, settings=request_settings)
        tx.execute(
            update_stmt,
            {"$user_id": user_id, "$now": current_time},
            settings=request_settings,
        )
        tx.commit()
        return {"status": 200}

    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error(
            "auth_manager.reset_sessions.error",
            phone=phone_number,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 200:
        logger.info("auth_manager.reset_sessions.success", phone=phone_number)
        return ok({"message": "All sessions have been reset.", "phone_number": phone_number})

    if result.get("status") == 404:
        return not_found("User not found.")

    if result.get("status") == 401:
        return unauthorized(result.get("message"))

    if result.get("status") == 423:
        return json_response(423, {"message": result.get("message")})

    return server_error("Unexpected error.")