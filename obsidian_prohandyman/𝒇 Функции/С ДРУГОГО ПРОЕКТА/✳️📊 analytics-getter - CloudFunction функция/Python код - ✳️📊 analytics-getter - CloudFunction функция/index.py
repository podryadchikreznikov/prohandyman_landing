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
    ACTION_OBJECT_FINANCE_HISTORY,
    ACTION_OBJECT_ACTIVITY_PRESENCE,
    ACTION_MY_OBJECT_PRESENCE,
    ACTION_OBJECT_ACTIVITY_TIMELINE,
    ACTION_FINANCE_TURNOVER,
    ACTION_FINANCE_GROSS_PROFIT,
    ACTION_FINANCE_OBJECTS_SUMMARY,
    ACTION_EMPLOYEE_ABSENCES_TOTAL,
    ACTION_EMPLOYEE_ABSENCES_DISPUTED,
    ACTION_EMPLOYEE_ABSENCES_MONTH,
    ACTION_EMPLOYEE_ABSENCES_MONTH_DETAILS,
    ACTION_EMPLOYEE_TIME_TOTAL,
    ACTION_EMPLOYEE_TIME_MONTH,
    ACTION_EMPLOYEE_TIME_MONTH_OBJECT,
    ACTION_EMPLOYEE_TIME_DAYS_MONTH,
    ACTION_EMPLOYEE_TIME_DAYS_MONTH_OBJECT,
    ACTION_EMPLOYEE_TIME_DAY_TIMELINE,
    ACTION_EMPLOYEE_TIME_DAY_OBJECT_TIMELINE,
    ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY,
    ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS,
    ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD,
    ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING,
    ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
    ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL,
    ACTION_EMPLOYEE_FINANCE_TOTAL,
    ACTION_EMPLOYEE_FINANCE_CASH_PLAN,
    ACTION_PAYROLL_QUEUE,
    ACTION_PAYROLL_HISTORY,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_TOTAL,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_PERCENT_AVG,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_TOTAL,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_PERCENT_AVG,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL_ALL_FIRMS,
    ACTION_DISPATCHER_SETTLEMENT_QUEUE,
    ACTION_WORKER_MONTH_WORK,
    ACTION_WORKER_DAY_WORK_ALL_FIRMS,
    ACTION_WORKER_MONTH_WORK_ALL_FIRMS,
    ACTION_WORKER_FINES_YEAR_TOTAL,
    ACTION_WORKER_FINES_MONTH_LIST,
    ACTION_WORKER_FINES_YEAR_LIST_EXCLUDING_MONTH,
    ACTION_WORKER_FINES_TOTALS_ALL_FIRMS,
    ACTION_WORKER_FINES_LIST_ALL_FIRMS,
    ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS,
    endpoint_for_action,
)
from handlers import (
    handle_object_finance_history,
    handle_object_activity_presence,
    handle_my_object_presence,
    handle_object_activity_timeline,
    handle_finance_turnover,
    handle_finance_gross_profit,
    handle_finance_objects_summary,
    handle_employee_absences_total,
    handle_employee_absences_disputed,
    handle_employee_absences_month,
    handle_employee_absences_month_details,
    handle_employee_time_total,
    handle_employee_time_month,
    handle_employee_time_month_object,
    handle_employee_time_days_month,
    handle_employee_time_days_month_object,
    handle_employee_time_day_timeline,
    handle_employee_time_day_object_timeline,
    handle_employee_attendance_month_summary,
    handle_employee_attendance_day_details,
    handle_employee_calendar_day_period,
    handle_employee_calendar_day_upcoming,
    handle_employee_finance_month_list,
    handle_employee_finance_month_total,
    handle_employee_finance_total,
    handle_employee_finance_cash_plan,
    handle_payroll_queue,
    handle_payroll_history,
    handle_dispatcher_withhold_accrual_year_total,
    handle_dispatcher_withhold_accrual_year_percent_avg,
    handle_dispatcher_withhold_accrual_month_total,
    handle_dispatcher_withhold_accrual_month_percent_avg,
    handle_dispatcher_withhold_accrual_user_total,
    handle_dispatcher_withhold_accrual_user_total_all_firms,
    handle_dispatcher_settlement_queue,
    handle_worker_month_deals_and_shifts,
    handle_worker_day_deals_and_shifts_all_firms,
    handle_worker_month_deals_and_shifts_all_firms,
    handle_worker_fines_year_total,
    handle_worker_fines_month_list,
    handle_worker_fines_year_list_excluding_month,
    handle_worker_fines_totals_all_firms,
    handle_worker_fines_list_all_firms,
    handle_worker_absences_list_all_firms,
)
from sa import get_ydb_credentials


hard_logger = YCLogger(
    stream_name=os.environ.get("LOG_STREAM_NAME", "analytics-getter"),
    hard_symbol=os.environ.get("HARD_LOG_SYMBOL", "📊"),
)

LOG_PREFIX = ""
LOG_CONTEXT_ARROW = "→"
_POOL_CACHE = {}
_POOL_LOCK = threading.Lock()
_ALLOWED_INTERNAL_SERVICES = {"analytics-getter"}


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
    ACTION_OBJECT_FINANCE_HISTORY,
    ACTION_OBJECT_ACTIVITY_PRESENCE,
    ACTION_MY_OBJECT_PRESENCE,
    ACTION_OBJECT_ACTIVITY_TIMELINE,
    ACTION_FINANCE_TURNOVER,
    ACTION_FINANCE_GROSS_PROFIT,
    ACTION_FINANCE_OBJECTS_SUMMARY,
    ACTION_EMPLOYEE_ABSENCES_TOTAL,
    ACTION_EMPLOYEE_ABSENCES_DISPUTED,
    ACTION_EMPLOYEE_ABSENCES_MONTH,
    ACTION_EMPLOYEE_ABSENCES_MONTH_DETAILS,
    ACTION_EMPLOYEE_TIME_TOTAL,
    ACTION_EMPLOYEE_TIME_MONTH,
    ACTION_EMPLOYEE_TIME_MONTH_OBJECT,
    ACTION_EMPLOYEE_TIME_DAYS_MONTH,
    ACTION_EMPLOYEE_TIME_DAYS_MONTH_OBJECT,
    ACTION_EMPLOYEE_TIME_DAY_TIMELINE,
    ACTION_EMPLOYEE_TIME_DAY_OBJECT_TIMELINE,
    ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY,
    ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS,
    ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD,
    ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING,
    ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
    ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL,
    ACTION_EMPLOYEE_FINANCE_TOTAL,
    ACTION_EMPLOYEE_FINANCE_CASH_PLAN,
    ACTION_PAYROLL_QUEUE,
    ACTION_PAYROLL_HISTORY,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_TOTAL,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_PERCENT_AVG,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_TOTAL,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_PERCENT_AVG,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL,
    ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL_ALL_FIRMS,
    ACTION_DISPATCHER_SETTLEMENT_QUEUE,
    ACTION_WORKER_MONTH_WORK,
    ACTION_WORKER_DAY_WORK_ALL_FIRMS,
    ACTION_WORKER_MONTH_WORK_ALL_FIRMS,
    ACTION_WORKER_FINES_YEAR_TOTAL,
    ACTION_WORKER_FINES_MONTH_LIST,
    ACTION_WORKER_FINES_YEAR_LIST_EXCLUDING_MONTH,
    ACTION_WORKER_FINES_TOTALS_ALL_FIRMS,
    ACTION_WORKER_FINES_LIST_ALL_FIRMS,
    ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS,
}


def handler(event, context):
    logger = JsonLogger(correlation_id=getattr(context, "request_id", None))
    hlog = hard_logger.bind(
        request_id=getattr(context, "request_id", None),
        function=getattr(context, "function_name", None),
    )
    hlog.hard("→handler_start", event_preview=YCLogger.preview(event, 4000))
    logger.info(
        _log_title("analytics_getter.context", has_context=True),
        context=safe_json(
            {
                "request_id": getattr(context, "request_id", None),
                "function_name": getattr(context, "function_name", None),
                "memory_limit_in_mb": getattr(context, "memory_limit_in_mb", None),
                "deadline_ms": getattr(context, "deadline_ms", None),
            }
        ),
    )
    logger.info(_log_title("analytics_getter.raw_event", has_context=True), event=safe_json(event))
    logger.info(_log_title("analytics_getter.invoked"))

    try:
        req = parse_event(event)
    except EventParseError as e:
        logger.warn(_log_title("analytics_getter.parse_error"), error=str(e))
        return bad_request(str(e))

    logger.info(
        _log_title("analytics_getter.request_parsed", has_context=True),
        headers=safe_json(req.get("headers")),
        query=safe_json(req.get("query")),
        path_params=safe_json(req.get("path_params")),
        action=req.get("action"),
        body_text=req.get("body_text"),
        body_dict=safe_json(req.get("body_dict")),
    )

    auth_ctx = get_authorizer_context(event)
    auth_type = str(auth_ctx.get("auth_type") or "").strip().lower()
    service_name = str(auth_ctx.get("service_name") or auth_ctx.get("principal_id") or "").strip()
    if auth_type == "internal_service":
        if service_name not in _ALLOWED_INTERNAL_SERVICES:
            logger.warn(_log_title("analytics_getter.auth.forbidden_internal_service"), service_name=service_name)
            return unauthorized("Unauthorized")
    elif auth_type != "employee_jwt":
        logger.warn(_log_title("analytics_getter.auth.invalid_context"), auth_type=auth_type)
        return unauthorized("Unauthorized")

    caller_user_id = str(auth_ctx.get("user_id") or auth_ctx.get("principal_id") or "").strip()
    caller_role_type = str(auth_ctx.get("role_type") or "").strip().lower() or None
    if not caller_user_id:
        logger.warn(_log_title("analytics_getter.auth.missing_user_id"))
        return unauthorized("Unauthorized")
    logger.info(_log_title("analytics_getter.caller"), caller_user_id=caller_user_id)

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
    if not action:
        action = req.get("action")
        if action:
            body["action"] = action
    
    if action not in VALID_ACTIONS:
        logger.warn(_log_title("analytics_getter.invalid_action"), action=action)
        return bad_request(
            "Invalid action. Expected one of: " + ", ".join(sorted(VALID_ACTIONS))
        )

    path_params = req.get("path_params") or {}
    path_firm_id = path_params.get("firm_id") if isinstance(path_params, dict) else None
    if isinstance(path_firm_id, str) and path_firm_id.strip() and not body.get("firm_id"):
        body["firm_id"] = path_firm_id.strip()

    endpoint = endpoint_for_action(action)
    try:
        expected_req_hash, expected_res_hash = get_expected_schema_hashes(
            logger,
            code_file=__file__,
            endpoint=endpoint,
        )
    except Exception as e:
        logger.error(_log_title("analytics_getter.schema_hashes_error"), error=str(e))
        hlog.exception("analytics_getter.schema_hashes_error", error=str(e))
        return server_error("Internal Server Error")

    contract_error = check_contract(body, logger, "analytics_getter", expected_req_hash, expected_res_hash)
    if contract_error:
        return contract_error

    firm_id = body.get("firm_id")
    if not isinstance(firm_id, str) or not firm_id.strip():
        logger.warn(_log_title("analytics_getter.validation_error"), field="firm_id", value=safe_json(firm_id))
        return bad_request("firm_id is required")
    firm_id = firm_id.strip()
    if not is_uuid(firm_id):
        logger.warn(_log_title("analytics_getter.validation_error"), field="firm_id", value=safe_json(firm_id))
        return bad_request("firm_id must be a valid UUID")

    if isinstance(path_firm_id, str) and path_firm_id.strip() and path_firm_id.strip() != firm_id:
        logger.warn(
            _log_title("analytics_getter.validation_error"),
            field="firm_id",
            value=safe_json(firm_id),
            path_firm_id=safe_json(path_firm_id),
        )
        return bad_request("firm_id must match path.firm_id")

    requires_appeals = action in {
        ACTION_EMPLOYEE_ABSENCES_DISPUTED,
        ACTION_EMPLOYEE_ABSENCES_MONTH_DETAILS,
        ACTION_WORKER_FINES_LIST_ALL_FIRMS,
        ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS,
        ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY,
        ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS,
        ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD,
        ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING,
    }
    uses_optional_appeals = action in {
        ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
        ACTION_PAYROLL_QUEUE,
    }

    requires_objects = action in {
        ACTION_OBJECT_FINANCE_HISTORY,
        ACTION_OBJECT_ACTIVITY_PRESENCE,
        ACTION_MY_OBJECT_PRESENCE,
        ACTION_FINANCE_TURNOVER,
        ACTION_FINANCE_GROSS_PROFIT,
        ACTION_FINANCE_OBJECTS_SUMMARY,
        ACTION_EMPLOYEE_ABSENCES_MONTH_DETAILS,
        ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
        ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL,
        ACTION_EMPLOYEE_FINANCE_TOTAL,
        ACTION_EMPLOYEE_FINANCE_CASH_PLAN,
        ACTION_PAYROLL_QUEUE,
        ACTION_WORKER_DAY_WORK_ALL_FIRMS,
        ACTION_WORKER_MONTH_WORK_ALL_FIRMS,
        ACTION_WORKER_FINES_LIST_ALL_FIRMS,
        ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS,
        ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY,
        ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS,
        ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD,
        ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING,
    }

    requires_firms = action in {
        ACTION_OBJECT_FINANCE_HISTORY,
        ACTION_OBJECT_ACTIVITY_PRESENCE,
        ACTION_MY_OBJECT_PRESENCE,
        ACTION_OBJECT_ACTIVITY_TIMELINE,
        ACTION_FINANCE_TURNOVER,
        ACTION_FINANCE_GROSS_PROFIT,
        ACTION_FINANCE_OBJECTS_SUMMARY,
        ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
        ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL,
        ACTION_EMPLOYEE_FINANCE_TOTAL,
        ACTION_EMPLOYEE_FINANCE_CASH_PLAN,
        ACTION_PAYROLL_QUEUE,
        ACTION_PAYROLL_HISTORY,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_TOTAL,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_PERCENT_AVG,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_TOTAL,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_PERCENT_AVG,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL_ALL_FIRMS,
        ACTION_WORKER_DAY_WORK_ALL_FIRMS,
        ACTION_WORKER_MONTH_WORK_ALL_FIRMS,
        ACTION_WORKER_FINES_TOTALS_ALL_FIRMS,
        ACTION_WORKER_FINES_LIST_ALL_FIRMS,
        ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS,
        ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY,
        ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS,
        ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD,
        ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING,
    }

    requires_events = True

    requires_notices = action in {
        ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
        ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL,
        ACTION_EMPLOYEE_FINANCE_CASH_PLAN,
        ACTION_PAYROLL_QUEUE,
    }

    requires_meta = action in {
        ACTION_OBJECT_FINANCE_HISTORY,
        ACTION_OBJECT_ACTIVITY_PRESENCE,
        ACTION_MY_OBJECT_PRESENCE,
        ACTION_OBJECT_ACTIVITY_TIMELINE,
        ACTION_FINANCE_TURNOVER,
        ACTION_FINANCE_GROSS_PROFIT,
        ACTION_FINANCE_OBJECTS_SUMMARY,
        ACTION_EMPLOYEE_ABSENCES_TOTAL,
        ACTION_EMPLOYEE_ABSENCES_DISPUTED,
        ACTION_EMPLOYEE_ABSENCES_MONTH,
        ACTION_EMPLOYEE_ABSENCES_MONTH_DETAILS,
        ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY,
        ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS,
        ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD,
        ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING,
        ACTION_EMPLOYEE_FINANCE_MONTH_LIST,
        ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL,
        ACTION_EMPLOYEE_FINANCE_TOTAL,
        ACTION_EMPLOYEE_FINANCE_CASH_PLAN,
        ACTION_PAYROLL_QUEUE,
        ACTION_PAYROLL_HISTORY,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_TOTAL,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_PERCENT_AVG,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_TOTAL,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_PERCENT_AVG,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL,
        ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL_ALL_FIRMS,
        ACTION_WORKER_MONTH_WORK,
        ACTION_WORKER_DAY_WORK_ALL_FIRMS,
        ACTION_WORKER_MONTH_WORK_ALL_FIRMS,
        ACTION_WORKER_FINES_YEAR_TOTAL,
        ACTION_WORKER_FINES_MONTH_LIST,
        ACTION_WORKER_FINES_YEAR_LIST_EXCLUDING_MONTH,
        ACTION_WORKER_FINES_TOTALS_ALL_FIRMS,
        ACTION_WORKER_FINES_LIST_ALL_FIRMS,
        ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS,
    }

    try:
        ydb_creds = get_ydb_credentials(logger)
        objects_endpoint = os.environ.get("YDB_ENDPOINT_FIRM_OBJECTS")
        objects_database = os.environ.get("YDB_DATABASE_FIRM_OBJECTS")
        firms_endpoint = os.environ.get("YDB_ENDPOINT_FIRMS")
        firms_database = os.environ.get("YDB_DATABASE_FIRMS")
        events_endpoint = os.environ.get("YDB_ENDPOINT_EVENTS_LOG")
        events_database = os.environ.get("YDB_DATABASE_EVENTS_LOG")
        appeals_endpoint = os.environ.get("YDB_ENDPOINT_APPEALS")
        appeals_database = os.environ.get("YDB_DATABASE_APPEALS")
        meta_endpoint = os.environ.get("YDB_ENDPOINT_META")
        meta_database = os.environ.get("YDB_DATABASE_META")
        notices_endpoint = os.environ.get("YDB_ENDPOINT_NOTICES")
        notices_database = os.environ.get("YDB_DATABASE_NOTICES")

        if requires_objects and (not objects_endpoint or not objects_database):
            raise RuntimeError("YDB_ENDPOINT_FIRM_OBJECTS/YDB_DATABASE_FIRM_OBJECTS not configured")
        if requires_firms and (not firms_endpoint or not firms_database):
            raise RuntimeError("YDB_ENDPOINT_FIRMS/YDB_DATABASE_FIRMS not configured")
        if requires_events and (not events_endpoint or not events_database):
            raise RuntimeError("YDB_ENDPOINT_EVENTS_LOG/YDB_DATABASE_EVENTS_LOG not configured")
        if requires_meta and (not meta_endpoint or not meta_database):
            raise RuntimeError("YDB_ENDPOINT_META/YDB_DATABASE_META not configured")
        if requires_notices and (not notices_endpoint or not notices_database):
            raise RuntimeError("YDB_ENDPOINT_NOTICES/YDB_DATABASE_NOTICES not configured")
        objects_pool = None
        firms_pool = None
        events_pool = None
        appeals_pool = None
        meta_pool = None
        notices_pool = None
        if requires_appeals and (not appeals_endpoint or not appeals_database):
            raise RuntimeError("YDB_ENDPOINT_APPEALS/YDB_DATABASE_APPEALS not configured")

        logger.info(
            _log_title("analytics_getter.env", has_context=True),
            objects_endpoint=objects_endpoint if requires_objects else None,
            objects_database=objects_database if requires_objects else None,
            firms_endpoint=firms_endpoint if requires_firms else None,
            firms_database=firms_database if requires_firms else None,
            events_endpoint=events_endpoint if requires_events else None,
            events_database=events_database if requires_events else None,
            appeals_endpoint=appeals_endpoint,
            appeals_database=appeals_database,
            meta_endpoint=meta_endpoint if requires_meta else None,
            meta_database=meta_database if requires_meta else None,
            notices_endpoint=notices_endpoint if requires_notices else None,
            notices_database=notices_database if requires_notices else None,
        )

        if requires_objects:
            objects_pool = _get_cached_pool(
                endpoint=objects_endpoint,
                database=objects_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
        if requires_firms:
            firms_pool = _get_cached_pool(
                endpoint=firms_endpoint,
                database=firms_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
        if requires_events:
            events_pool = _get_cached_pool(
                endpoint=events_endpoint,
                database=events_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
        if requires_appeals or (uses_optional_appeals and appeals_endpoint and appeals_database):
            appeals_pool = _get_cached_pool(
                endpoint=appeals_endpoint,
                database=appeals_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
        if requires_meta:
            meta_pool = _get_cached_pool(
                endpoint=meta_endpoint,
                database=meta_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
        if requires_notices:
            notices_pool = _get_cached_pool(
                endpoint=notices_endpoint,
                database=notices_database,
                credentials=ydb_creds,
                wait_timeout_sec=30.0,
            )
    except Exception as e:
        logger.error(
            _log_title("analytics_getter.config_error"),
            error=str(e),
            trace=traceback.format_exc(),
        )
        hlog.exception("analytics_getter.config_error", error=str(e))
        return server_error("Internal Server Error")

    if action == ACTION_OBJECT_FINANCE_HISTORY:
        return handle_object_finance_history(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_OBJECT_ACTIVITY_PRESENCE:
        return handle_object_activity_presence(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_MY_OBJECT_PRESENCE:
        return handle_my_object_presence(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_OBJECT_ACTIVITY_TIMELINE:
        return handle_object_activity_timeline(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_FINANCE_TURNOVER:
        return handle_finance_turnover(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_FINANCE_GROSS_PROFIT:
        return handle_finance_gross_profit(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_FINANCE_OBJECTS_SUMMARY:
        return handle_finance_objects_summary(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            caller_role_type=caller_role_type,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_ABSENCES_TOTAL:
        return handle_employee_absences_total(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_ABSENCES_DISPUTED:
        return handle_employee_absences_disputed(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_ABSENCES_MONTH:
        return handle_employee_absences_month(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_ABSENCES_MONTH_DETAILS:
        return handle_employee_absences_month_details(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_TOTAL:
        return handle_employee_time_total(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_MONTH:
        return handle_employee_time_month(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_MONTH_OBJECT:
        return handle_employee_time_month_object(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_DAYS_MONTH:
        return handle_employee_time_days_month(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_DAYS_MONTH_OBJECT:
        return handle_employee_time_days_month_object(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_DAY_TIMELINE:
        return handle_employee_time_day_timeline(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_TIME_DAY_OBJECT_TIMELINE:
        return handle_employee_time_day_object_timeline(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_ATTENDANCE_MONTH_SUMMARY:
        return handle_employee_attendance_month_summary(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_ATTENDANCE_DAY_DETAILS:
        return handle_employee_attendance_day_details(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_CALENDAR_DAY_PERIOD:
        return handle_employee_calendar_day_period(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_CALENDAR_DAY_UPCOMING:
        return handle_employee_calendar_day_upcoming(
            body=body,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_FINANCE_MONTH_LIST:
        return handle_employee_finance_month_list(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_FINANCE_MONTH_TOTAL:
        return handle_employee_finance_month_total(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_FINANCE_TOTAL:
        return handle_employee_finance_total(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_EMPLOYEE_FINANCE_CASH_PLAN:
        return handle_employee_finance_cash_plan(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_PAYROLL_QUEUE:
        return handle_payroll_queue(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_PAYROLL_HISTORY:
        return handle_payroll_history(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_TOTAL:
        return handle_dispatcher_withhold_accrual_year_total(
            body=body,
            firm_id=firm_id,
            dispatcher_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_WITHHOLD_ACCRUAL_YEAR_PERCENT_AVG:
        return handle_dispatcher_withhold_accrual_year_percent_avg(
            body=body,
            firm_id=firm_id,
            dispatcher_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_TOTAL:
        return handle_dispatcher_withhold_accrual_month_total(
            body=body,
            firm_id=firm_id,
            dispatcher_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_WITHHOLD_ACCRUAL_MONTH_PERCENT_AVG:
        return handle_dispatcher_withhold_accrual_month_percent_avg(
            body=body,
            firm_id=firm_id,
            dispatcher_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL:
        return handle_dispatcher_withhold_accrual_user_total(
            body=body,
            firm_id=firm_id,
            dispatcher_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_WITHHOLD_ACCRUAL_USER_TOTAL_ALL_FIRMS:
        return handle_dispatcher_withhold_accrual_user_total_all_firms(
            body=body,
            firm_id=firm_id,
            dispatcher_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_DISPATCHER_SETTLEMENT_QUEUE:
        return handle_dispatcher_settlement_queue(
            body=body,
            firm_id=firm_id,
            events_pool=events_pool,
            events_database=events_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_MONTH_WORK:
        return handle_worker_month_deals_and_shifts(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_DAY_WORK_ALL_FIRMS:
        return handle_worker_day_deals_and_shifts_all_firms(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_MONTH_WORK_ALL_FIRMS:
        return handle_worker_month_deals_and_shifts_all_firms(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_FINES_YEAR_TOTAL:
        return handle_worker_fines_year_total(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_FINES_MONTH_LIST:
        return handle_worker_fines_month_list(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_FINES_YEAR_LIST_EXCLUDING_MONTH:
        return handle_worker_fines_year_list_excluding_month(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_FINES_TOTALS_ALL_FIRMS:
        return handle_worker_fines_totals_all_firms(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_FINES_LIST_ALL_FIRMS:
        return handle_worker_fines_list_all_firms(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    if action == ACTION_WORKER_ABSENCES_LIST_ALL_FIRMS:
        return handle_worker_absences_list_all_firms(
            body=body,
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            events_pool=events_pool,
            events_database=events_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            hlog=hlog,
        )

    return bad_request("Unsupported action")
