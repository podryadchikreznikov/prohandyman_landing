# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional, Tuple

import ydb

from utils import JsonLogger, bad_request, created, server_error
from utils.util_log import YCLogger

from common import is_uuid
from constants import EVENT_CASH
from events_helper import create_event_entity
from features.salary import _read_employee_salary_snapshot, _update_salary_last_payout_at
from handlers import _ensure_employee_exists, _format_money_kopeks, _send_notice_safe, _server_now_iso


def _parse_cash_payment_breakdown(
    *,
    body: dict,
    total_amount_kopeks: int,
    salary_snapshot: List[Dict[str, Any]],
    paid_at: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    payment_scope = body.get("payment_scope")
    if not isinstance(payment_scope, str) or not payment_scope.strip():
        return None, "payment_scope is required"
    payment_scope = payment_scope.strip().lower()
    if payment_scope not in {"salary", "rewards_fines", "all"}:
        return None, "payment_scope must be one of: salary, rewards_fines, all"

    raw_salary_items = body.get("salary_payment_items")
    if raw_salary_items is None:
        raw_salary_items = []
    if not isinstance(raw_salary_items, list):
        return None, "salary_payment_items must be an array"

    salary_snapshot_by_id = {
        str(item.get("salary_id") or "").strip(): item
        for item in salary_snapshot
        if str(item.get("salary_id") or "").strip()
    }
    salary_payment_items: List[Dict[str, Any]] = []
    for item in raw_salary_items:
        if not isinstance(item, dict):
            return None, "salary_payment_items items must be objects"
        salary_id = str(item.get("salary_id") or "").strip()
        if not salary_id:
            return None, "salary_payment_items[].salary_id is required"
        if not is_uuid(salary_id):
            return None, "salary_payment_items[].salary_id must be a valid UUID"
        if salary_id not in salary_snapshot_by_id:
            return None, "salary_payment_items[].salary_id must reference employee_salary_snapshot"
        amount_kopeks = item.get("amount_kopeks")
        if not isinstance(amount_kopeks, int) or amount_kopeks < 0:
            return None, "salary_payment_items[].amount_kopeks must be a non-negative integer"
        salary_ref = salary_snapshot_by_id.get(salary_id) or {}
        salary_payment_items.append(
            {
                "salary_id": salary_id,
                "paid_at": paid_at,
                "amount_kopeks": amount_kopeks,
                "salary_payout_date": salary_ref.get("payout_date"),
            }
        )

    raw_rewards_fines = body.get("rewards_fines_payment")
    rewards_fines_payment = None
    if raw_rewards_fines is not None:
        if not isinstance(raw_rewards_fines, dict):
            return None, "rewards_fines_payment must be an object"
        rf_amount_kopeks = raw_rewards_fines.get("amount_kopeks")
        if not isinstance(rf_amount_kopeks, int) or rf_amount_kopeks < 0:
            return None, "rewards_fines_payment.amount_kopeks must be a non-negative integer"
        rewards_fines_payment = {
            "paid_at": paid_at,
            "amount_kopeks": rf_amount_kopeks,
        }

    if payment_scope in {"salary", "all"} and not salary_payment_items:
        return None, "salary_payment_items is required for payment_scope=salary|all"
    if payment_scope in {"rewards_fines", "all"} and rewards_fines_payment is None:
        return None, "rewards_fines_payment is required for payment_scope=rewards_fines|all"
    if payment_scope == "salary" and rewards_fines_payment is not None:
        return None, "rewards_fines_payment must be omitted for payment_scope=salary"
    if payment_scope == "rewards_fines" and salary_payment_items:
        return None, "salary_payment_items must be omitted for payment_scope=rewards_fines"

    salary_total_kopeks = sum(int(item.get("amount_kopeks", 0) or 0) for item in salary_payment_items)
    rewards_fines_total_kopeks = int((rewards_fines_payment or {}).get("amount_kopeks", 0) or 0)

    if payment_scope == "salary":
        breakdown_total_kopeks = salary_total_kopeks
    elif payment_scope == "rewards_fines":
        breakdown_total_kopeks = rewards_fines_total_kopeks
    else:
        breakdown_total_kopeks = salary_total_kopeks + rewards_fines_total_kopeks

    if breakdown_total_kopeks != total_amount_kopeks:
        return None, (
            "amount_kopeks must be equal to payment breakdown total: "
            f"{breakdown_total_kopeks}"
        )

    payment_components: List[Dict[str, Any]] = []
    for item in salary_payment_items:
        payment_components.append(
            {
                "component_type": "salary",
                "salary_id": item.get("salary_id"),
                "salary_payout_date": item.get("salary_payout_date"),
                "paid_at": item.get("paid_at"),
                "amount_kopeks": item.get("amount_kopeks"),
            }
        )
    if rewards_fines_payment is not None:
        payment_components.append(
            {
                "component_type": "rewards_fines",
                "paid_at": rewards_fines_payment.get("paid_at"),
                "amount_kopeks": rewards_fines_payment.get("amount_kopeks"),
            }
        )

    return (
        {
            "payment_scope": payment_scope,
            "salary_payment_items": salary_payment_items,
            "rewards_fines_payment": rewards_fines_payment,
            "payment_components": payment_components,
            "salary_total_kopeks": salary_total_kopeks,
            "rewards_fines_total_kopeks": rewards_fines_total_kopeks,
            "breakdown_total_kopeks": breakdown_total_kopeks,
        },
        None,
    )


def handle_cash_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    user_id = body.get("user_id")
    user_name = body.get("user_name")
    amount_kopeks = body.get("amount_kopeks")
    accrual_event_id_raw = body.get("accrual_event_id")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not isinstance(user_name, str) or not user_name.strip():
        return bad_request("user_name is required")
    if not isinstance(amount_kopeks, int) or amount_kopeks < 0:
        return bad_request("amount_kopeks must be a non-negative integer")
    event_at = _server_now_iso()

    accrual_event_id = None
    if accrual_event_id_raw is not None:
        if not isinstance(accrual_event_id_raw, str) or not accrual_event_id_raw.strip():
            return bad_request("accrual_event_id must be a non-empty string")
        accrual_event_id = accrual_event_id_raw.strip()
        if not is_uuid(accrual_event_id):
            return bad_request("accrual_event_id must be a valid UUID")

    user_id = user_id.strip()

    exists_error = _ensure_employee_exists(
        firm_id=firm_id,
        user_id=user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
    )
    if exists_error:
        return exists_error

    try:
        salary_snapshot = _read_employee_salary_snapshot(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            user_id=user_id,
            active_only=True,
            as_of=event_at,
        )
    except Exception as e:
        logger.error("payroll_manager.cash.salary_snapshot_read_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.cash.salary_snapshot_read_failed", error=str(e))
        return server_error("Internal Server Error")

    payment_breakdown, payment_breakdown_error = _parse_cash_payment_breakdown(
        body=body,
        total_amount_kopeks=amount_kopeks,
        salary_snapshot=salary_snapshot,
        paid_at=event_at,
    )
    if payment_breakdown_error:
        return bad_request(payment_breakdown_error)

    payload = {
        "firm_id": firm_id,
        "user_id": user_id,
        "user_name": user_name.strip(),
        "amount_kopeks": amount_kopeks,
        "event_at": event_at,
        "payment_scope": payment_breakdown.get("payment_scope"),
        "salary_payment_items": payment_breakdown.get("salary_payment_items"),
        "rewards_fines_payment": payment_breakdown.get("rewards_fines_payment"),
        "payment_components": payment_breakdown.get("payment_components"),
        "salary_total_kopeks": payment_breakdown.get("salary_total_kopeks"),
        "rewards_fines_total_kopeks": payment_breakdown.get("rewards_fines_total_kopeks"),
        "employee_salary_snapshot": salary_snapshot,
    }
    if accrual_event_id:
        payload["accrual_event_id"] = accrual_event_id

    try:
        event_id = create_event_entity(user_id, EVENT_CASH, payload, logger, firm_id=firm_id, schema_version=3)
    except Exception as e:
        logger.error("payroll_manager.cash.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.cash.event_failed", error=str(e))
        return server_error("Event generation failed")
    try:
        _update_salary_last_payout_at(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            salary_payment_items=payment_breakdown.get("salary_payment_items") or [],
        )
    except Exception as e:
        logger.error("payroll_manager.cash.salary_last_payout_update_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.cash.salary_last_payout_update_failed", error=str(e))
        return server_error("Internal Server Error")
    try:
        _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="you_received_payout",
            data={
                "firm_id": firm_id,
                "user_id": user_id,
                "amount_text": _format_money_kopeks(amount_kopeks),
            },
        )
    except Exception as e:
        logger.error("payroll_manager.cash.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.cash.notice_failed", error=str(e))

    return created(
        {
            "message": "Cash payout created",
            "event_id": event_id,
            "firm_id": firm_id,
            "user_id": user_id,
        }
    )
