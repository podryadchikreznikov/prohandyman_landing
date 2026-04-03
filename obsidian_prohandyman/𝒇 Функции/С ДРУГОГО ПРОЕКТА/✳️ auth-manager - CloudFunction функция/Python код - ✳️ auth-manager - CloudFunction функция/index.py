# -*- coding: utf-8 -*-
import os
import json
import ydb

from utils.util_log import YCLogger

from utils import parse_event, EventParseError, JsonLogger, validate_phone_number, bad_request, server_error, check_contract, get_expected_schema_hashes
from utils.util_ydb.driver import get_session_pool
from utils.util_yc_sa import get_sa_key_dict_from_lockbox
from utils.util_yc_sa.loader import YcSaLoader


def _action_to_suffix(action: str) -> str:
    return {
        "login": "login",
        "register": "register",
        "resend_code": "resend-code",
        "verify_code": "verify-code",
        "reset_password": "reset-password",
        "reset_sessions": "reset-sessions",
    }.get(action)


from common import VALID_ACTIONS, generate_code, get_table_name, get_user_type
from get_user_data import handle_get_user_data
from login import handle_login
from register import handle_register
from resend_code import handle_resend_code
from reset_password import handle_reset_password
from reset_sessions import handle_reset_sessions
from verify_code import handle_verify_code


hard_logger = YCLogger(
    stream_name=os.environ.get("LOG_STREAM_NAME", "auth-manager"),
    hard_symbol=os.environ.get("HARD_LOG_SYMBOL", "🧨"),
)


_CREDENTIALS_CACHE = None

_POOL_CACHE = None
_META_POOL_CACHE = None


def _resolve_meta_ydb() -> tuple[str, str]:
    endpoint = os.environ.get("YDB_ENDPOINT_META")
    database = os.environ.get("YDB_DATABASE_META")
    if not endpoint or not database:
        raise RuntimeError("YDB_ENDPOINT_META/YDB_DATABASE_META not configured")
    return endpoint, database


def _get_sa_credentials(logger: JsonLogger) -> ydb.iam.ServiceAccountCredentials:
    global _CREDENTIALS_CACHE
    if _CREDENTIALS_CACHE:
        return _CREDENTIALS_CACHE

    secret_id = os.environ.get("SA_AUTHKEY_LOCKBOX_SECRET_NAME")
    if not secret_id:
        logger.error("config.missing_env", var="SA_AUTHKEY_LOCKBOX_SECRET_NAME")
        raise RuntimeError("SA_AUTHKEY_LOCKBOX_SECRET_NAME is required")

    sa_key_dict = get_sa_key_dict_from_lockbox(secret_id)
    _CREDENTIALS_CACHE = YcSaLoader.make_ydb_credentials_from_sa_key_dict(sa_key_dict)
    return _CREDENTIALS_CACHE


def handler(event, context):
    logger = JsonLogger()
    hlog = hard_logger.bind(
        request_id=getattr(context, "request_id", None),
        function=getattr(context, "function_name", None),
    )
    hlog.hard("→handler_start", event_preview=YCLogger.preview(event, 4000))

    logger.info("auth_manager.start")

    auto_confirm_mode = os.environ.get("AUTO_CONFIRM_MODE", "false").lower() == "true"

    try:
        req = parse_event(event)
        data = req.get("body_dict") or {}
    except EventParseError as e:
        logger.error("auth_manager.parse_error", error=str(e))
        hlog.warn("auth_manager.parse_error", error=str(e))
        return bad_request(str(e))

    headers = req.get("headers") or {}
    if isinstance(data, dict) and not isinstance(data.get("contract"), dict):
        req_hash = headers.get("x-request-schema-hash")
        res_hash = headers.get("x-response-schema-hash")
        if req_hash or res_hash:
            data["contract"] = {
                "request_schema_hash": req_hash,
                "response_schema_hash": res_hash,
            }

    action = (data.get("action") or "").strip().lower()
    if not action:
        return bad_request("action is required.")
    if action not in VALID_ACTIONS:
        return bad_request("Invalid action.")

    user_type = get_user_type(event)

    suffix = _action_to_suffix(action)
    if not suffix or user_type not in ("user", "dispatcher"):
        return bad_request("Invalid action.")

    endpoint = f"/auth/{user_type}/{suffix}"
    expected_req_hash, expected_res_hash = get_expected_schema_hashes(logger, code_file=__file__, endpoint=endpoint)
    contract_error = check_contract(data, logger, "auth_manager", expected_req_hash, expected_res_hash)
    if contract_error:
        return contract_error

    phone_number = None
    if action != "get_user_data":
        phone_number_raw = (data.get("phone_number") or "").strip() if data.get("phone_number") else None
        phone_number = validate_phone_number(phone_number_raw) if phone_number_raw else None
        if not phone_number:
            return bad_request("Valid phone_number is required.")

    password = data.get("password")
    new_password = data.get("new_password")
    code = data.get("code")

    if action in ("login", "register", "reset_sessions") and not password:
        return bad_request("password is required.")
    if action == "reset_password" and not new_password:
        return bad_request("new_password is required.")
    if action == "verify_code" and not code:
        return bad_request("code is required.")

    try:
        ydb_creds = _get_sa_credentials(logger)
        endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        database = os.environ.get("YDB_DATABASE_FIRMS")
        jwt_secret = os.environ.get("JWT_SECRET")

        meta_endpoint, meta_database = _resolve_meta_ydb()

        if not endpoint or not database or not jwt_secret:
            raise RuntimeError("YDB/JWT env not configured")

        global _POOL_CACHE, _META_POOL_CACHE
        if _POOL_CACHE is None:
            _POOL_CACHE = get_session_pool(endpoint, database, credentials=ydb_creds, wait_timeout_sec=15.0)
        if _META_POOL_CACHE is None:
            _META_POOL_CACHE = get_session_pool(meta_endpoint, meta_database, credentials=ydb_creds, wait_timeout_sec=15.0)

        pool = _POOL_CACHE
        meta_pool = _META_POOL_CACHE
    except Exception as e:
        logger.error("auth_manager.config_error", error=str(e))
        hlog.exception("auth_manager.config_error", error=str(e))
        return server_error("Internal Server Error")

    table_name = get_table_name(user_type)
    logger.info("auth_manager.context", action=action, user_type=user_type, table_name=table_name)

    verification_code = generate_code()

    if action == "login":
        return handle_login(
            pool=pool,
            database=database,
            table_name=table_name,
            phone_number=phone_number,
            password=password,
            verification_code=verification_code,
            auto_confirm_mode=auto_confirm_mode,
            jwt_secret=jwt_secret,
            logger=logger,
        )

    if action == "get_user_data":
        return handle_get_user_data(
            pool=pool,
            database=database,
            table_name=table_name,
            req=req,
            event=event,
            jwt_secret=jwt_secret,
            logger=logger,
        )

    if action == "register":
        return handle_register(
            pool=pool,
            database=database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            table_name=table_name,
            phone_number=phone_number,
            password=password,
            verification_code=verification_code,
            auto_confirm_mode=auto_confirm_mode,
            jwt_secret=jwt_secret,
            logger=logger,
        )

    if action == "resend_code":
        return handle_resend_code(
            pool=pool,
            database=database,
            table_name=table_name,
            phone_number=phone_number,
            verification_code=verification_code,
            auto_confirm_mode=auto_confirm_mode,
            logger=logger,
        )

    if action == "verify_code":
        return handle_verify_code(
            pool=pool,
            database=database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            table_name=table_name,
            phone_number=phone_number,
            code=code,
            jwt_secret=jwt_secret,
            logger=logger,
        )

    if action == "reset_password":
        return handle_reset_password(
            pool=pool,
            database=database,
            table_name=table_name,
            phone_number=phone_number,
            new_password=new_password,
            verification_code=verification_code,
            auto_confirm_mode=auto_confirm_mode,
            logger=logger,
        )

    if action == "reset_sessions":
        return handle_reset_sessions(
            pool=pool,
            database=database,
            table_name=table_name,
            phone_number=phone_number,
            password=password,
            logger=logger,
        )

    return bad_request("Unknown action")