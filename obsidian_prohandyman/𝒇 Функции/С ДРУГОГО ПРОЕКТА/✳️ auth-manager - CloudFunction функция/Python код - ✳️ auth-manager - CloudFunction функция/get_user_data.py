# -*- coding: utf-8 -*-
import traceback

import ydb

from utils import (
    get_authorizer_context,
    ok,
    bad_request,
    unauthorized,
    not_found,
    server_error,
)
from common import build_request_settings

def _resolve_user_id(*, req, event, jwt_secret: str):
    body = req.get("body_dict") or {}
    query = req.get("query") or {}

    user_id = (body.get("user_id") or query.get("user_id") or "").strip()
    if user_id:
        return user_id

    auth_ctx = get_authorizer_context(event)
    user_id = str(auth_ctx.get("user_id") or auth_ctx.get("principal_id") or "").strip()
    if not user_id:
        raise ValueError("missing_authorizer_context")
    return user_id


def handle_get_user_data(*, pool, database: str, table_name: str, req, event, jwt_secret: str, logger):
    try:
        user_id = _resolve_user_id(req=req, event=event, jwt_secret=jwt_secret)
    except ValueError as e:
        if str(e) == "missing_authorizer_context":
            return unauthorized("Authorization context missing")
        return bad_request("user_id is required")
    except Exception as e:
        logger.error(
            "auth_manager.get_user_data.resolve_user_id_error",
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    def transaction(session: ydb.Session):
        request_settings = build_request_settings()
        q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $user_id AS Utf8;
            SELECT
                user_id,
                email,
                phone_number,
                status,
                last_login_at,
                created_at,
                updated_at
            FROM {table_name}
            WHERE user_id = $user_id;
        """
        stmt = session.prepare(q, settings=request_settings)
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            stmt,
            {"$user_id": user_id},
            commit_tx=True,
            settings=request_settings,
        )

        if not rs[0].rows:
            return {"status": 404}

        row = rs[0].rows[0]
        return {
            "status": 200,
            "user": {
                "user_id": getattr(row, "user_id", None),
                "email": getattr(row, "email", None),
                "phone_number": getattr(row, "phone_number", None),
                "status": getattr(row, "status", None),
                "last_login_at": getattr(row, "last_login_at", None),
                "created_at": getattr(row, "created_at", None),
                "updated_at": getattr(row, "updated_at", None),
            },
        }

    try:
        result = pool.retry_operation_sync(transaction)
    except Exception as e:
        logger.error(
            "auth_manager.get_user_data.error",
            user_id=user_id,
            error=str(e),
            trace=traceback.format_exc(),
        )
        return server_error("Internal Server Error")

    if result.get("status") == 404:
        return not_found("User not found.")

    return ok(result.get("user") or {})
