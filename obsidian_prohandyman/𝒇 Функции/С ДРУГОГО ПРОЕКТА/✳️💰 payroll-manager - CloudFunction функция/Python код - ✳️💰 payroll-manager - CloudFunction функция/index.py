# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import threading
import traceback

from utils.util_log import YCLogger
from utils import (
    EventParseError,
    JsonLogger,
    bad_request,
    check_contract,
    get_expected_schema_hashes,
    get_authorizer_context,
    parse_event,
    server_error,
    unauthorized,
)
from utils.util_ydb.driver import get_session_pool

from common import is_uuid, safe_json
from constants import (
    ACTION_ACCRUAL_CREATE,
    ACTION_CASH_CREATE,
    ACTION_DEFERRED_CREATE,
    ACTION_DISPATCHER_SETTLEMENT_CREATE,
    ACTION_FINE_CREATE,
    ACTION_REWARD_CREATE,
    ACTION_SALARY_DELETE,
    ACTION_SALARY_UPSERT,
    endpoint_for_action,
)
from features.accrual import handle_accrual_create
from features.cash import handle_cash_create
from features.deferred import handle_deferred_create
from features.dispatcher_settlement import handle_dispatcher_settlement_create
from features.fine_reward import handle_fine_create, handle_reward_create
from features.salary import handle_salary_delete, handle_salary_upsert
from handlers import (
    ensure_caller_access,
)
from sa import get_ydb_credentials

hard_logger = YCLogger(
    stream_name=os.environ.get("LOG_STREAM_NAME", "payroll-manager"),
    hard_symbol=os.environ.get("HARD_LOG_SYMBOL", "🧨"),
)

LOG_PREFIX = ""
LOG_CONTEXT_ARROW = "→"
_POOL_CACHE = {}
_POOL_LOCK = threading.Lock()


def _extract_authorizer_identity(event) -> dict | None:
    authorizer = get_authorizer_context(event)
    if not isinstance(authorizer, dict) or not authorizer:
        return None

    required_fields = ("auth_type", "user_id", "firm_id", "role_type")
    identity = {}
    for field in required_fields:
        value = authorizer.get(field)
        if not isinstance(value, str) or not value.strip():
            return None
        identity[field] = value.strip()

    principal_id = authorizer.get("principal_id")
    if isinstance(principal_id, str) and principal_id.strip():
        identity["principal_id"] = principal_id.strip()
    principal_type = authorizer.get("principal_type")
    if isinstance(principal_type, str) and principal_type.strip():
        identity["principal_type"] = principal_type.strip()
    email = authorizer.get("email")
    if isinstance(email, str) and email.strip():
        identity["email"] = email.strip()

    return identity


def _log_title(message: str, *, has_context: bool = False) -> str:
    prefix = LOG_PREFIX
    if has_context:
        prefix = f"{prefix} {LOG_CONTEXT_ARROW}"
    return f"{prefix} {message}"


def _get_cached_pool(*, endpoint: str, database: str, credentials, wait_timeout_sec: float = 30.0):
    cache_key = f"{endpoint}|{database}"
    cached_pool = _POOL_CACHE.get(cache_key)
    if cached_pool is not None:
        return cached_pool

    with _POOL_LOCK:
        cached_pool = _POOL_CACHE.get(cache_key)
        if cached_pool is not None:
            return cached_pool
        pool = get_session_pool(
            endpoint,
            database,
            credentials=credentials,
            wait_timeout_sec=wait_timeout_sec,
        )
        _POOL_CACHE[cache_key] = pool
        return pool


VALID_ACTIONS = {
    ACTION_ACCRUAL_CREATE,
    ACTION_DEFERRED_CREATE,
    ACTION_CASH_CREATE,
    ACTION_SALARY_UPSERT,
    ACTION_SALARY_DELETE,
    ACTION_FINE_CREATE,
    ACTION_REWARD_CREATE,
    ACTION_DISPATCHER_SETTLEMENT_CREATE,
}


def handler(event, context):
    logger = JsonLogger(correlation_id=getattr(context, "request_id", None))
    hlog = hard_logger.bind(
        request_id=getattr(context, "request_id", None),
        function=getattr(context, "function_name", None),
    )
    hlog.hard("→handler_start", event_preview=YCLogger.preview(event, 4000))
    logger.info(
        _log_title("payroll_manager.context", has_context=True),
        context=safe_json(
            {
                "request_id": getattr(context, "request_id", None),
                "function_name": getattr(context, "function_name", None),
                "memory_limit_in_mb": getattr(context, "memory_limit_in_mb", None),
                "deadline_ms": getattr(context, "deadline_ms", None),
            }
        ),
    )
    logger.info(_log_title("payroll_manager.raw_event", has_context=True), event=safe_json(event))
    logger.info(_log_title("payroll_manager.invoked"))

    try:
        req = parse_event(event)
    except EventParseError as e:
        logger.warn(_log_title("payroll_manager.parse_error"), error=str(e))
        return bad_request(str(e))

    logger.info(
        _log_title("payroll_manager.request_parsed", has_context=True),
        headers=safe_json(req.get("headers")),
        query=safe_json(req.get("query")),
        path_params=safe_json(req.get("path_params")),
        action=req.get("action"),
        body_text=req.get("body_text"),
        body_dict=safe_json(req.get("body_dict")),
    )

    identity = _extract_authorizer_identity(event)
    if not identity:
        logger.warn(_log_title("payroll_manager.auth.missing_authorizer_context"))
        return unauthorized("Unauthorized")

    if identity.get("auth_type") != "employee_jwt":
        logger.warn(
            _log_title("payroll_manager.auth.invalid_identity_type"),
            auth_type=identity.get("auth_type"),
            principal_type=identity.get("principal_type"),
        )
        return unauthorized("Unauthorized")

    caller_user_id = identity.get("user_id")
    caller_role_type = identity.get("role_type")
    authorizer_firm_id = identity.get("firm_id")
    logger.info(
        _log_title("payroll_manager.caller"),
        caller_user_id=caller_user_id,
        caller_role_type=caller_role_type,
        authorizer_firm_id=authorizer_firm_id,
    )

    body = req.get("body_dict") or {}
    headers = req.get("headers") or {}
    if isinstance(body, dict):
        req_hash = headers.get("x-request-schema-hash")
        res_hash = headers.get("x-response-schema-hash")
        if req_hash or res_hash:
            contract = body.get("contract")
            if not isinstance(contract, dict):
                contract = {}
            contract.setdefault("request_schema_hash", req_hash)
            contract.setdefault("response_schema_hash", res_hash)
            body["contract"] = contract

    action = body.get("action")
    if action not in VALID_ACTIONS:
        logger.warn(_log_title("payroll_manager.invalid_action"), action=action)
        return bad_request("Invalid action. Expected one of: " + ", ".join(sorted(VALID_ACTIONS)))

    endpoint = endpoint_for_action(action)
    try:
        expected_req_hash, expected_res_hash = get_expected_schema_hashes(
            logger,
            code_file=__file__,
            endpoint=endpoint,
        )
    except Exception as e:
        logger.error(_log_title("payroll_manager.schema_hashes_error"), error=str(e))
        hlog.exception("payroll_manager.schema_hashes_error", error=str(e))
        return server_error("Internal Server Error")

    contract_error = check_contract(body, logger, "payroll_manager", expected_req_hash, expected_res_hash)
    if contract_error:
        return contract_error

    firm_id = body.get("firm_id")
    if not isinstance(firm_id, str) or not firm_id.strip():
        logger.warn(_log_title("payroll_manager.validation_error"), field="firm_id", value=safe_json(firm_id))
        return bad_request("firm_id is required")
    firm_id = firm_id.strip()
    if not is_uuid(firm_id):
        logger.warn(_log_title("payroll_manager.validation_error"), field="firm_id", value=safe_json(firm_id))
        return bad_request("firm_id must be a valid UUID")

    if authorizer_firm_id != firm_id:
        logger.warn(
            _log_title("payroll_manager.validation_error"),
            field="authorizer.firm_id",
            value=safe_json(authorizer_firm_id),
            firm_id=safe_json(firm_id),
        )
        return unauthorized("Unauthorized")

    path_params = req.get("path_params") or {}
    path_firm_id = path_params.get("firm_id") if isinstance(path_params, dict) else None
    if isinstance(path_firm_id, str) and path_firm_id.strip() and path_firm_id.strip() != firm_id:
        logger.warn(
            _log_title("payroll_manager.validation_error"),
            field="firm_id",
            value=safe_json(firm_id),
            path_firm_id=safe_json(path_firm_id),
        )
        return bad_request("firm_id must match path.firm_id")

    try:
        ydb_creds = get_ydb_credentials(logger)
        firms_endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        firms_database = os.environ.get("YDB_DATABASE_FIRMS")
        notices_endpoint = os.environ.get("YDB_ENDPOINT_NOTICES")
        notices_database = os.environ.get("YDB_DATABASE_NOTICES")
        events_endpoint = os.environ.get("YDB_ENDPOINT_EVENTS_LOG")
        events_database = os.environ.get("YDB_DATABASE_EVENTS_LOG")
        meta_endpoint = os.environ.get("YDB_ENDPOINT_META")
        meta_database = os.environ.get("YDB_DATABASE_META")

        if not firms_endpoint or not firms_database:
            raise RuntimeError("YDB_ENDPOINT_FIRMS/YDB_DATABASE_FIRMS not configured")
        if not notices_endpoint or not notices_database:
            raise RuntimeError("YDB_ENDPOINT_NOTICES/YDB_DATABASE_NOTICES not configured")
        if action in {ACTION_ACCRUAL_CREATE, ACTION_DISPATCHER_SETTLEMENT_CREATE} and (not events_endpoint or not events_database):
            raise RuntimeError("YDB_ENDPOINT_EVENTS_LOG/YDB_DATABASE_EVENTS_LOG not configured")
        if action in {ACTION_ACCRUAL_CREATE, ACTION_DISPATCHER_SETTLEMENT_CREATE} and (not meta_endpoint or not meta_database):
            raise RuntimeError("YDB_ENDPOINT_META/YDB_DATABASE_META not configured")

        logger.info(
            _log_title("payroll_manager.env", has_context=True),
            firms_endpoint=firms_endpoint,
            firms_database=firms_database,
            notices_endpoint=notices_endpoint,
            notices_database=notices_database,
            events_endpoint=events_endpoint,
            events_database=events_database,
            meta_endpoint=meta_endpoint,
            meta_database=meta_database,
        )

        firms_pool = _get_cached_pool(
            endpoint=firms_endpoint,
            database=firms_database,
            credentials=ydb_creds,
            wait_timeout_sec=30.0,
        )
        notices_pool = _get_cached_pool(
            endpoint=notices_endpoint,
            database=notices_database,
            credentials=ydb_creds,
            wait_timeout_sec=30.0,
        )
        events_pool = None
        meta_pool = None
        if action in {ACTION_ACCRUAL_CREATE, ACTION_DISPATCHER_SETTLEMENT_CREATE}:
            events_pool = _get_cached_pool(
                endpoint=events_endpoint,
                database=events_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
            meta_pool = _get_cached_pool(
                endpoint=meta_endpoint,
                database=meta_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
    except Exception as e:
        logger.error(
            _log_title("payroll_manager.config_error"),
            error=str(e),
            trace=traceback.format_exc(),
        )
        hlog.exception("payroll_manager.config_error", error=str(e))
        return server_error("Internal Server Error")

    access_error = ensure_caller_access(
        firm_id=firm_id,
        caller_user_id=caller_user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
    )
    if access_error:
        return access_error

    if action == ACTION_SALARY_UPSERT:
        return handle_salary_upsert(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_SALARY_DELETE:
        return handle_salary_delete(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DEFERRED_CREATE:
        return handle_deferred_create(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_ACCRUAL_CREATE:
        return handle_accrual_create(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_CASH_CREATE:
        return handle_cash_create(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_FINE_CREATE:
        return handle_fine_create(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_REWARD_CREATE:
        return handle_reward_create(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_SETTLEMENT_CREATE:
        return handle_dispatcher_settlement_create(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            firms_pool=firms_pool,
            firms_database=firms_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    return bad_request("Unsupported action")
