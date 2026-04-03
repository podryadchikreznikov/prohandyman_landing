# -*- coding: utf-8 -*-
import traceback

import ydb

from utils import issue_jwt, now_utc, ok, not_found, bad_request, server_error

from common import build_request_settings, normalize_timestamp


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


def handle_verify_code(
    *,
    pool,
    database: str,
    meta_pool,
    meta_database: str,
    table_name: str,
    phone_number: str,
    code: str,
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
            SELECT user_id, verification_code, verification_expires_at, jwt_token
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

        stored_code = getattr(row, "verification_code", None)
        if stored_code != code:
            tx.rollback()
            return {"status": 400, "message": "Invalid code."}

        expires_dt = normalize_timestamp(getattr(row, "verification_expires_at", None))
        if expires_dt and current_time > expires_dt:
            tx.rollback()
            return {"status": 400, "message": "Code expired."}

        stored_token = getattr(row, "jwt_token", None)
        if stored_token:
            update_q = f"""
                PRAGMA TablePathPrefix('{database}');
                DECLARE $user_id AS Utf8;
                DECLARE $now AS Timestamp;
                UPDATE {table_name}
                SET status = 'active',
                    verification_code = NULL,
                    verification_expires_at = NULL,
                    last_login_at = $now,
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
            return {"status": 200, "token": stored_token, "user_id": user_id}

        token = issue_jwt(user_id, secret=jwt_secret, claims={"phone_number": phone_number})

        update_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $user_id AS Utf8;
            DECLARE $token AS Utf8;
            DECLARE $now AS Timestamp;
            UPDATE {table_name}
            SET status = 'active',
                jwt_token = $token,
                verification_code = NULL,
                verification_expires_at = NULL,
                last_login_at = $now,
                updated_at = $now
            WHERE user_id = $user_id;
        """
        update_stmt = session.prepare(update_q, settings=request_settings)
        tx.execute(
            update_stmt,
            {"$user_id": user_id, "$token": token, "$now": current_time},
            settings=request_settings,
        )
        tx.commit()
        return {"status": 200, "token": token, "user_id": user_id}

    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error(
            "auth_manager.verify_code.error",
            phone=phone_number,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 200:
        try:
            if isinstance(result.get("user_id"), str) and result.get("user_id"):
                _ensure_aggregate_state_table(meta_pool, meta_database, result["user_id"], logger)
        except Exception as e:
            logger.error(
                "auth_manager.meta.aggregate_state_table_error",
                error=str(e),
                trace=traceback.format_exc(),
            )
            return server_error("Internal Server Error")
        logger.info("auth_manager.verify_code.success", phone=phone_number)
        return ok({"token": result["token"]})

    if result.get("status") == 404:
        return not_found("User not found.")

    if result.get("status") == 400:
        return bad_request(result.get("message", "Invalid or expired code."))

    return server_error("Unexpected error.")