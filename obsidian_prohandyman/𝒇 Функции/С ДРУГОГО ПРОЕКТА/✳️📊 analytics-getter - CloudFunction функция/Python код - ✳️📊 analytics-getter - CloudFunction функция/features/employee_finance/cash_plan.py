# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from utils import bad_request, ok_response, server_error

from event_state import fetch_firm_event_states
from handlers_dispatcher_settlement import (
    _build_open_debts_by_worker as _build_dispatcher_open_debts_by_worker,
    _calculate_dispatcher_withheld_kopeks,
    _collect_dispatcher_settlement_events,
    _extract_dispatcher_snapshot_from_shift_event,
    _shift_snapshot_matches_scope,
)
from handlers_employee_finance import (
    CASH_PLAN_EVENT_TYPES_SQL,
    NEGATIVE_PENDING_TYPES,
    REWARDS_FINES_SOURCE_TYPES,
    _build_salary_balance_summary,
    _build_work_item_amount_context,
    _collect_cash_finance_summary,
    _collect_employee_events,
    _enrich_work_item_amounts,
    _event_created_at,
    _filter_salary_snapshot_for_current_period,
    _latest_event_of_type,
    _norm_text,
    _parse_as_of,
    _read_employee_salary_snapshot,
    _read_finance_event_rows,
    _safe_int,
    _to_iso_date,
    _to_iso_utc,
)
from handlers_payroll import (
    _build_open_dispatcher_debts_by_scope,
    _collect_dispatcher_settlement_events_by_scope,
    _extract_shift_dispatcher_scope_from_event,
    _read_user_names,
)


_DISPATCHER_PLAN_EVENT_TYPES_SQL = ", ".join(
    sorted(
        {
            normalized
            for raw in ("shift_end", "dispatcher_settlement")
            for normalized in (
                f"'{str(raw).strip()}'",
                f"'{str(raw).strip().lower()}'",
                f"'{str(raw).strip().upper()}'",
            )
            if normalized
        }
    )
)


def _build_dispatcher_settlement_plan(
    *,
    firm_id: str,
    user_id: str,
    as_of: datetime,
    events_pool,
    events_database: str,
    objects_pool,
    objects_database: str,
    firms_pool,
    firms_database: str,
    meta_pool,
    meta_database: str,
    logger,
) -> Optional[Dict[str, Any]]:
    start_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end_at = as_of + timedelta(seconds=1)
    event_rows = _read_finance_event_rows(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start=start_at,
        end=end_at,
        event_types_sql=_DISPATCHER_PLAN_EVENT_TYPES_SQL,
    )
    if not event_rows:
        return None

    event_ids = [row["event_id"] for row in event_rows if _norm_text(row.get("event_id"))]
    states_by_event_id = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )
    worker_events = _collect_employee_events(
        event_rows=event_rows,
        states_by_event_id=states_by_event_id,
        user_id=user_id,
    )
    worker_events = _enrich_work_item_amounts(
        events=worker_events,
        amount_context=_build_work_item_amount_context(
            events=worker_events,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        ),
        logger=logger,
    )
    settlement_events_by_scope = _collect_dispatcher_settlement_events_by_scope(
        event_rows=event_rows,
        states_by_event_id=states_by_event_id,
    )
    open_debts_by_scope = _build_open_dispatcher_debts_by_scope(
        settlement_events_by_scope,
    )

    candidate_scope_keys: set[tuple[str, Optional[str]]] = set()
    for scope_key, debts_by_user in open_debts_by_scope.items():
        if debts_by_user.get(user_id):
            candidate_scope_keys.add(scope_key)
    for event in worker_events:
        if _norm_text(event.get("event_type_upper")) != "SHIFT_END":
            continue
        shift_scope = _extract_shift_dispatcher_scope_from_event(event)
        if shift_scope is None:
            continue
        candidate_scope_keys.add((shift_scope[0], shift_scope[1]))

    if not candidate_scope_keys:
        return None

    dispatcher_ids = sorted(
        {
            scope_key[1]
            for scope_key in candidate_scope_keys
            if scope_key[0] == "dispatcher" and scope_key[1]
        }
    )
    dispatcher_names = (
        _read_user_names(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=dispatcher_ids,
        )
        if dispatcher_ids
        else {}
    )

    best_plan: Optional[Dict[str, Any]] = None
    best_activity_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for attribution_type, dispatcher_id in candidate_scope_keys:
        scope_events = _collect_dispatcher_settlement_events(
            event_rows=event_rows,
            states_by_event_id=states_by_event_id,
            attribution_type=attribution_type,
            dispatcher_id=dispatcher_id,
        )
        last_scope_event = scope_events[-1] if scope_events else None
        lower_bound = _event_created_at(last_scope_event) if last_scope_event else None
        open_debts_by_worker = _build_dispatcher_open_debts_by_worker(scope_events)
        previous_debts = list(open_debts_by_worker.get(user_id) or [])
        previous_debt_kopeks = sum(
            max(_safe_int(item.get("remaining_kopeks"), 0) or 0, 0)
            for item in previous_debts
        )

        shifts: List[Dict[str, Any]] = []
        last_activity_at = _event_created_at(last_scope_event) if last_scope_event else datetime(1970, 1, 1, tzinfo=timezone.utc)
        percent_snapshot = 0.0
        dispatcher_name = dispatcher_names.get(dispatcher_id) if dispatcher_id else None
        for event in worker_events:
            if _norm_text(event.get("event_type_upper")) != "SHIFT_END":
                continue
            if lower_bound is not None and _event_created_at(event) <= lower_bound:
                continue
            amount_kopeks = event.get("amount_kopeks")
            if not isinstance(amount_kopeks, int):
                continue
            snapshot = _extract_dispatcher_snapshot_from_shift_event(event)
            if not _shift_snapshot_matches_scope(
                snapshot,
                attribution_type=attribution_type,
                dispatcher_id=dispatcher_id,
            ):
                continue
            state = event.get("state") if isinstance(event.get("state"), dict) else {}
            gross_amount_kopeks = abs(amount_kopeks)
            percent_snapshot = float((snapshot or {}).get("percent_snapshot") or 0.0)
            if not dispatcher_name:
                dispatcher_name = (snapshot or {}).get("dispatcher_name")
            event_created_at = _event_created_at(event)
            if event_created_at > last_activity_at:
                last_activity_at = event_created_at
            shifts.append(
                {
                    "shift_event_id": _norm_text(event.get("event_id")),
                    "shift_id": _norm_text(state.get("shift_id")) or None,
                    "object_id": _norm_text(event.get("object_id")) or None,
                    "object_name": None,
                    "created_at": _to_iso_utc(event.get("created_at")),
                    "event_at": _norm_text(state.get("event_at")) or None,
                    "dispatcher_id": (snapshot or {}).get("dispatcher_id"),
                    "dispatcher_name": (snapshot or {}).get("dispatcher_name"),
                    "attribution_type": (snapshot or {}).get("attribution_type"),
                    "gross_amount_kopeks": gross_amount_kopeks,
                    "percent_snapshot": percent_snapshot,
                    "withheld_amount_kopeks": _calculate_dispatcher_withheld_kopeks(
                        gross_amount_kopeks,
                        percent_snapshot,
                    ),
                }
            )

        current_period_due_kopeks = sum(
            max(_safe_int(item.get("withheld_amount_kopeks"), 0) or 0, 0)
            for item in shifts
        )
        amount_due_kopeks = current_period_due_kopeks + previous_debt_kopeks
        if amount_due_kopeks <= 0:
            continue
        if not shifts and isinstance(last_scope_event, dict):
            last_workers = (last_scope_event.get("state") or {}).get("workers") or []
            for last_worker in last_workers:
                if not isinstance(last_worker, dict):
                    continue
                if _norm_text(last_worker.get("worker_user_id")) != user_id:
                    continue
                percent_snapshot = float(last_worker.get("percent_snapshot") or 0.0)
                break

        plan = {
            "dispatcher_id": dispatcher_id,
            "dispatcher_name": dispatcher_name,
            "attribution_type": attribution_type,
            "percent_snapshot": percent_snapshot,
            "period_started_at": _to_iso_utc(lower_bound) if lower_bound else None,
            "period_ended_at": _to_iso_utc(as_of),
            "source_last_settlement_event_id": _norm_text((last_scope_event or {}).get("event_id")) or None,
            "source_last_settlement_created_at": _to_iso_utc((last_scope_event or {}).get("created_at")),
            "current_period_due_kopeks": current_period_due_kopeks,
            "previous_debt_kopeks": previous_debt_kopeks,
            "amount_due_kopeks": amount_due_kopeks,
            "amount_remaining_kopeks": amount_due_kopeks,
            "shifts_count": len(shifts),
            "previous_debts_count": len(previous_debts),
            "shifts": shifts,
            "previous_debts": previous_debts,
        }
        if best_plan is None or last_activity_at > best_activity_at:
            best_plan = plan
            best_activity_at = last_activity_at

    return best_plan


def handle_employee_finance_cash_plan(
    body,
    firm_id,
    events_pool,
    events_database,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    notices_pool,
    notices_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_finance_cash_plan.start", firm_id=firm_id)

    user_id = _norm_text(body.get("user_id"))
    if not user_id:
        return bad_request("user_id is required")

    as_of, as_of_error = _parse_as_of(body)
    if as_of_error:
        return bad_request(as_of_error)
    if as_of is None:
        return bad_request("as_of must be a valid ISO datetime")

    try:
        logger.info(
            "analytics_getter.employee_finance_cash_plan.dependencies",
            firm_id=firm_id,
            has_events_pool=events_pool is not None,
            has_firms_pool=firms_pool is not None,
            has_notices_pool=notices_pool is not None,
            has_meta_pool=meta_pool is not None,
            events_database=events_database,
            firms_database=firms_database,
            notices_database=notices_database,
            meta_database=meta_database,
        )
        start_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_at = as_of + timedelta(seconds=1)
        event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start_at,
            end=end_at,
            event_types_sql=CASH_PLAN_EVENT_TYPES_SQL,
        )

        event_ids = [row["event_id"] for row in event_rows if _norm_text(row.get("event_id"))]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )
        employee_events = _collect_employee_events(
            event_rows=event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        work_item_amount_context = _build_work_item_amount_context(
            events=employee_events,
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        employee_events = _enrich_work_item_amounts(
            events=employee_events,
            amount_context=work_item_amount_context,
            logger=logger,
        )
        salary_snapshot = _read_employee_salary_snapshot(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            user_id=user_id,
            as_of=as_of,
        )
        last_accrual = _latest_event_of_type(employee_events, "ACCRUAL")
        lower_bound = _event_created_at(last_accrual) if isinstance(last_accrual, dict) else None
        period_employee_events = [
            item
            for item in employee_events
            if lower_bound is None or _event_created_at(item) > lower_bound
        ]
        salary_snapshot = _filter_salary_snapshot_for_current_period(
            salary_snapshot=salary_snapshot,
            lower_bound=lower_bound,
            as_of=as_of,
        )

        rewards_fines_created_kopeks = 0

        for item in period_employee_events:
            event_type_upper = _norm_text(item.get("event_type_upper"))
            amount_kopeks = item.get("amount_kopeks")
            if event_type_upper == "CASH":
                continue

            if event_type_upper not in REWARDS_FINES_SOURCE_TYPES:
                continue
            if not isinstance(amount_kopeks, int):
                continue
            amount_abs = abs(amount_kopeks)
            if amount_abs <= 0:
                continue
            if event_type_upper in NEGATIVE_PENDING_TYPES:
                rewards_fines_created_kopeks -= amount_abs
            else:
                rewards_fines_created_kopeks += amount_abs

        all_cash_summary = _collect_cash_finance_summary(employee_events)
        period_cash_summary = _collect_cash_finance_summary(period_employee_events)
        rewards_fines_paid_kopeks = (
            _safe_int(period_cash_summary.get("rewards_fines_paid_kopeks"), 0) or 0
        )
        rewards_fines_balance_kopeks = rewards_fines_created_kopeks - rewards_fines_paid_kopeks
        rewards_fines_pending_kopeks = max(rewards_fines_balance_kopeks, 0)
        rewards_fines_overpaid_kopeks = max(-rewards_fines_balance_kopeks, 0)

        salary_summary = _build_salary_balance_summary(
            salary_snapshot=salary_snapshot,
            salary_paid_by_id=all_cash_summary.get("salary_paid_by_id") or {},
        )
        salary_total_kopeks = _safe_int(salary_summary.get("salary_total_kopeks"), 0) or 0
        salary_paid_kopeks = _safe_int(salary_summary.get("salary_paid_kopeks"), 0) or 0
        salary_total_remaining_kopeks = (
            _safe_int(salary_summary.get("salary_total_remaining_kopeks"), 0) or 0
        )
        salary_total_overpaid_kopeks = (
            _safe_int(salary_summary.get("salary_total_overpaid_kopeks"), 0) or 0
        )
        active_salary_items_count = (
            _safe_int(salary_summary.get("active_salary_items_count"), 0) or 0
        )
        salary_paid_without_snapshot_kopeks = (
            _safe_int(salary_summary.get("salary_paid_without_snapshot_kopeks"), 0) or 0
        )
        salary_paid_unknown_items = (
            salary_summary.get("salary_paid_unknown_items")
            if isinstance(salary_summary.get("salary_paid_unknown_items"), list)
            else []
        )

        salary_items: List[Dict[str, Any]] = []
        for salary in salary_summary.get("salary_items") or []:
            if not isinstance(salary, dict):
                continue
            salary_items.append(
                {
                    "salary_id": _norm_text(salary.get("salary_id")),
                    "amount_kopeks": _safe_int(salary.get("source_amount_kopeks"), 0) or 0,
                    "paid_kopeks": _safe_int(salary.get("paid_kopeks"), 0) or 0,
                    "remaining_kopeks": _safe_int(salary.get("remaining_kopeks"), 0) or 0,
                    "overpaid_kopeks": _safe_int(salary.get("overpaid_kopeks"), 0) or 0,
                    "status": _norm_text(salary.get("status")) or "active",
                    "effective_from": _to_iso_utc(salary.get("effective_from")),
                    "deleted_at": _to_iso_utc(salary.get("deleted_at")),
                    "payout_date": _to_iso_date(salary.get("payout_date")),
                    "last_payout_at": _to_iso_utc(salary.get("last_payout_at")),
                    "created_at": _to_iso_utc(salary.get("created_at")),
                    "updated_at": _to_iso_utc(salary.get("updated_at")),
                }
            )

        dispatcher_settlement = _build_dispatcher_settlement_plan(
            firm_id=firm_id,
            user_id=user_id,
            as_of=as_of,
            events_pool=events_pool,
            events_database=events_database,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        total_to_cover_all_kopeks = rewards_fines_pending_kopeks + salary_total_remaining_kopeks

        logger.info(
            "analytics_getter.employee_finance_cash_plan.success",
            firm_id=firm_id,
            user_id=user_id,
            events_count=len(employee_events),
            period_events_count=len(period_employee_events),
            source_last_accrual_event_id=_norm_text((last_accrual or {}).get("event_id")) or None,
            period_started_at=_to_iso_utc(lower_bound) if lower_bound else None,
            salary_items_count=len(salary_items),
            rewards_fines_created_kopeks=rewards_fines_created_kopeks,
            rewards_fines_paid_kopeks=rewards_fines_paid_kopeks,
            rewards_fines_pending_kopeks=rewards_fines_pending_kopeks,
            salary_total_remaining_kopeks=salary_total_remaining_kopeks,
            total_to_cover_all_kopeks=total_to_cover_all_kopeks,
            dispatcher_settlement_due_kopeks=_safe_int(
                (dispatcher_settlement or {}).get("amount_due_kopeks"),
                0,
            )
            or 0,
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "as_of": _to_iso_utc(as_of),
                "events_count": len(employee_events),
                "salary_items_count": len(salary_items),
                "active_salary_items_count": active_salary_items_count,
                "rewards_fines_created_kopeks": rewards_fines_created_kopeks,
                "rewards_fines_paid_kopeks": rewards_fines_paid_kopeks,
                "rewards_fines_balance_kopeks": rewards_fines_balance_kopeks,
                "rewards_fines_pending_kopeks": rewards_fines_pending_kopeks,
                "rewards_fines_overpaid_kopeks": rewards_fines_overpaid_kopeks,
                "salary_total_kopeks": salary_total_kopeks,
                "salary_paid_kopeks": salary_paid_kopeks,
                "salary_total_remaining_kopeks": salary_total_remaining_kopeks,
                "salary_total_overpaid_kopeks": salary_total_overpaid_kopeks,
                "salary_paid_without_snapshot_kopeks": salary_paid_without_snapshot_kopeks,
                "salary_paid_unknown_items": salary_paid_unknown_items,
                "total_to_cover_all_kopeks": total_to_cover_all_kopeks,
                "salary_items": salary_items,
                "dispatcher_settlement": dispatcher_settlement,
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_cash_plan.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_cash_plan.error", error=str(e))
        return server_error("Internal Server Error")
