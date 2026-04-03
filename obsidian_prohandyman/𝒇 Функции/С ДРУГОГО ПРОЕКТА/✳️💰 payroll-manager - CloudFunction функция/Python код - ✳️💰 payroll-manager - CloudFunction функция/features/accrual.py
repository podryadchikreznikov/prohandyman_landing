# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import ydb

from utils import JsonLogger, bad_request, created, parse_iso_utc, server_error
from utils.util_log import YCLogger

from common import is_uuid
from constants import EVENT_ACCRUAL
from events_helper import create_event_entity
from features.salary import _read_employee_salary_snapshot
from handlers import (
    _build_accrual_queue_item,
    _collect_user_finance_events,
    _ensure_employee_exists,
    _fetch_firm_event_states,
    _norm_text,
    _read_dispatcher_attribution_for_user,
    _read_finance_event_rows,
    _read_user_full_name,
    _server_now_iso,
)


def _read_accrual_queue_item(
    *,
    firm_id: str,
    user_id: str,
    event_at: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger: JsonLogger,
) -> Dict[str, Any]:
    try:
        as_of = parse_iso_utc(event_at)
    except Exception:
        raise RuntimeError("Invalid event_at for accrual snapshot build")

    salary_snapshot = _read_employee_salary_snapshot(
        notices_pool=notices_pool,
        notices_database=notices_database,
        firm_id=firm_id,
        user_id=user_id,
        as_of=event_at,
    )
    user_name = _read_user_full_name(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_id=user_id,
    ) or user_id
    dispatcher_attribution = _read_dispatcher_attribution_for_user(
        firms_pool=firms_pool,
        firms_database=firms_database,
        firm_id=firm_id,
        user_id=user_id,
    )

    event_rows = _read_finance_event_rows(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        end_at=as_of + timedelta(seconds=1),
    )
    event_ids = [_norm_text(item.get("event_id")) for item in event_rows if _norm_text(item.get("event_id"))]
    states_by_event_id = _fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )
    user_events = _collect_user_finance_events(
        event_rows=event_rows,
        states_by_event_id=states_by_event_id,
        user_id=user_id,
    )

    return _build_accrual_queue_item(
        firm_id=firm_id,
        user_id=user_id,
        user_name=user_name,
        salary_snapshot=salary_snapshot,
        user_events=user_events,
        dispatcher_attribution=dispatcher_attribution,
        as_of=as_of,
    )


def _build_accrual_payment_breakdown(
    *,
    total_amount_kopeks: int,
    salary_snapshot: List[Dict[str, Any]],
    event_at: str,
) -> Dict[str, Any]:
    normalized_total_amount = max(int(total_amount_kopeks or 0), 0)

    active_salary_snapshot = [
        item
        for item in salary_snapshot
        if isinstance(item, dict)
        and str(item.get("salary_id") or "").strip()
        and str(item.get("status") or "active").strip().lower() != "deleted"
    ]
    active_salary_snapshot.sort(
        key=lambda item: (
            str(item.get("payout_date") or ""),
            str(item.get("effective_from") or ""),
            str(item.get("salary_id") or ""),
        )
    )

    remaining_for_salary = normalized_total_amount
    salary_payment_items: List[Dict[str, Any]] = []
    for salary_item in active_salary_snapshot:
        if remaining_for_salary <= 0:
            break
        salary_amount_kopeks = max(int(salary_item.get("amount_kopeks") or 0), 0)
        if salary_amount_kopeks <= 0:
            continue
        allocated_amount_kopeks = min(salary_amount_kopeks, remaining_for_salary)
        if allocated_amount_kopeks <= 0:
            continue
        remaining_for_salary -= allocated_amount_kopeks
        salary_payment_items.append(
            {
                "salary_id": str(salary_item.get("salary_id") or "").strip(),
                "paid_at": event_at,
                "amount_kopeks": allocated_amount_kopeks,
                "salary_payout_date": salary_item.get("payout_date"),
            }
        )

    salary_total_kopeks = sum(int(item.get("amount_kopeks", 0) or 0) for item in salary_payment_items)
    rewards_fines_total_kopeks = max(remaining_for_salary, 0)

    if salary_total_kopeks > 0 and rewards_fines_total_kopeks > 0:
        payment_scope = "all"
    elif salary_total_kopeks > 0:
        payment_scope = "salary"
    else:
        payment_scope = "rewards_fines"

    rewards_fines_payment = None
    if payment_scope in {"rewards_fines", "all"}:
        rewards_fines_payment = {
            "paid_at": event_at,
            "amount_kopeks": rewards_fines_total_kopeks,
        }

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

    return {
        "payment_scope": payment_scope,
        "salary_payment_items": salary_payment_items,
        "rewards_fines_payment": rewards_fines_payment,
        "payment_components": payment_components,
        "salary_total_kopeks": salary_total_kopeks,
        "rewards_fines_total_kopeks": rewards_fines_total_kopeks,
    }


def _build_accrual_payload_from_queue_item(
    *,
    firm_id: str,
    user_id: str,
    event_at: str,
    queue_item: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_queue_item = (
        json.loads(json.dumps(queue_item, ensure_ascii=False))
        if isinstance(queue_item, dict)
        else {}
    )
    user_name = str(normalized_queue_item.get("user_name") or user_id).strip() or user_id
    amount_kopeks = max(int(normalized_queue_item.get("amount_kopeks") or 0), 0)

    raw_totals = (
        normalized_queue_item.get("totals")
        if isinstance(normalized_queue_item.get("totals"), dict)
        else {}
    )
    totals = {
        "salary_total_kopeks": int(raw_totals.get("salary_total_kopeks") or 0),
        "rewards_total_kopeks": int(raw_totals.get("rewards_total_kopeks") or 0),
        "deals_total_kopeks": int(raw_totals.get("deals_total_kopeks") or 0),
        "shifts_total_kopeks": int(raw_totals.get("shifts_total_kopeks") or 0),
        "fines_total_kopeks": int(raw_totals.get("fines_total_kopeks") or 0),
        "withholds_total_kopeks": int(raw_totals.get("withholds_total_kopeks") or 0),
        "events_total_count": int(raw_totals.get("events_total_count") or 0),
    }

    dispatcher_attribution = (
        normalized_queue_item.get("dispatcher_attribution")
        if isinstance(normalized_queue_item.get("dispatcher_attribution"), dict)
        else {"percent_snapshot": 0.0}
    )
    if "percent_snapshot" not in dispatcher_attribution:
        dispatcher_attribution = {
            **dispatcher_attribution,
            "percent_snapshot": 0.0,
        }

    deferred_state = (
        normalized_queue_item.get("deferred_state")
        if isinstance(normalized_queue_item.get("deferred_state"), dict)
        else {"is_deferred": False}
    )
    if "is_deferred" not in deferred_state:
        deferred_state = {
            **deferred_state,
            "is_deferred": False,
        }

    salary_snapshot = (
        normalized_queue_item.get("employee_salary_snapshot")
        if isinstance(normalized_queue_item.get("employee_salary_snapshot"), list)
        else []
    )

    payload = {
        "firm_id": firm_id,
        "user_id": user_id,
        "user_name": user_name,
        "amount_kopeks": amount_kopeks,
        "event_at": event_at,
        "period_ended_at": str(normalized_queue_item.get("period_ended_at") or event_at),
        "totals": totals,
        "dispatcher_attribution": dispatcher_attribution,
        "deferred_state": deferred_state,
        "employee_salary_snapshot": salary_snapshot,
        "fines": normalized_queue_item.get("fines")
        if isinstance(normalized_queue_item.get("fines"), list)
        else [],
        "rewards": normalized_queue_item.get("rewards")
        if isinstance(normalized_queue_item.get("rewards"), list)
        else [],
        "shifts": normalized_queue_item.get("shifts")
        if isinstance(normalized_queue_item.get("shifts"), list)
        else [],
        "deals": normalized_queue_item.get("deals")
        if isinstance(normalized_queue_item.get("deals"), list)
        else [],
        "withholds": normalized_queue_item.get("withholds")
        if isinstance(normalized_queue_item.get("withholds"), list)
        else [],
    }

    for key in (
        "period_started_at",
        "source_last_accrual_event_id",
        "source_last_accrual_created_at",
    ):
        value = normalized_queue_item.get(key)
        if isinstance(value, str) and value.strip():
            payload[key] = value

    return payload


def handle_accrual_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    user_id = body.get("user_id")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")

    user_id = user_id.strip()
    event_at = _server_now_iso()

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
        queue_item = _read_accrual_queue_item(
            firm_id=firm_id,
            user_id=user_id,
            event_at=event_at,
            firms_pool=firms_pool,
            firms_database=firms_database,
            notices_pool=notices_pool,
            notices_database=notices_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        if not isinstance(queue_item, dict):
            return server_error("Internal Server Error")
    except Exception as e:
        logger.error("payroll_manager.accrual.snapshot_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.accrual.snapshot_failed", error=str(e))
        return server_error("Internal Server Error")

    payload = _build_accrual_payload_from_queue_item(
        firm_id=firm_id,
        user_id=user_id,
        event_at=event_at,
        queue_item=queue_item,
    )

    try:
        event_id = create_event_entity(
            user_id,
            EVENT_ACCRUAL,
            payload,
            logger,
            firm_id=firm_id,
            schema_version=3,
        )
    except Exception as e:
        logger.error("payroll_manager.accrual.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.accrual.event_failed", error=str(e))
        return server_error("Event generation failed")

    return created(
        {
            "message": "Accrual created",
            "event_id": event_id,
            "firm_id": firm_id,
            "user_id": user_id,
        }
    )
