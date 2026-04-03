# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Set, Tuple

import ydb

from utils import bad_request, ok_response, server_error

from handlers_employee_finance import (
    _build_current_finance_snapshot,
    _build_response_events,
    _build_work_item_amount_context,
    _chunked,
    _collect_employee_events,
    _enrich_work_item_amounts,
    _extract_deferred_state,
    _extract_cash_rewards_fines_paid_kopeks,
    _extract_cash_salary_payment_items,
    _norm_text,
    _parse_as_of,
    _parse_page,
    _read_employee_salary_snapshot,
    _read_fine_disputes_by_event_ids,
    _read_finance_event_rows,
    _read_objects_by_ids,
    _safe_int,
    _to_iso_date,
    _to_iso_utc,
)
from event_state import extract_amount_kopeks, extract_user_id, fetch_firm_event_states

CURRENT_SOURCE_EVENT_TYPES = {
    "REWARD",
    "FINE",
    "SHIFT_END",
    "DEAL_COMPLETE",
}

HISTORY_STATUS_EVENT_TYPES = {"CASH"}


def _read_payroll_employees(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    filter_user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    allowed_roles = {"worker", "foreman", "foreman_foreman"}
    active_statuses = {"active_attached", "active_unattached"}

    def _tx(session: ydb.Session):
        where_filter = ""
        if filter_user_id:
            where_filter = "AND user_id = $user_id"
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        {"DECLARE $user_id AS Utf8;" if filter_user_id else ""}
        SELECT user_id, role_type, status
        FROM firm_employees
        WHERE firm_id = $firm_id
          {where_filter}
        ORDER BY role_type ASC, user_id ASC;
        """
        params = {"$firm_id": firm_id}
        if filter_user_id:
            params["$user_id"] = filter_user_id
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            params,
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            user_id = _norm_text(getattr(row, "user_id", None))
            role_type = _norm_text(getattr(row, "role_type", None)).lower()
            status = _norm_text(getattr(row, "status", None)).lower()
            if not user_id or role_type not in allowed_roles or status not in active_statuses:
                continue
            out.append(
                {
                    "user_id": user_id,
                    "role_type": role_type,
                    "status": status,
                }
            )

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_user_names(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    user_ids: List[str],
) -> Dict[str, str]:
    if not user_ids:
        return {}

    out: Dict[str, str] = {}
    unique_ids: List[str] = []
    seen: Set[str] = set()
    for user_id in user_ids:
        norm = _norm_text(user_id)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_ids.append(norm)

    if not unique_ids:
        return out

    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $user_ids AS List<Utf8>;
            SELECT user_id, full_name
            FROM UserProfiles
            WHERE user_id IN $user_ids;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$user_ids": chunk},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                user_id = _norm_text(getattr(row, "user_id", None))
                if not user_id:
                    continue
                out[user_id] = _norm_text(getattr(row, "full_name", None))

        firms_pool.retry_operation_sync(_tx)

    return out


def _read_dispatcher_attributions(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    user_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not user_ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    unique_ids: List[str] = []
    seen: Set[str] = set()
    for user_id in user_ids:
        norm = _norm_text(user_id)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_ids.append(norm)

    if not unique_ids:
        return out

    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_ids AS List<Utf8>;
            SELECT worker_user_id, dispatcher_id, percent_snapshot, attribution_type, created_at, updated_at
            FROM dispatcher_attributions
            WHERE firm_id = $firm_id
              AND worker_user_id IN $user_ids
            ORDER BY
                CASE
                    WHEN attribution_type = 'dispatcher' THEN 0
                    WHEN attribution_type = 'nominal' THEN 1
                    ELSE 2
                END ASC,
                updated_at DESC,
                created_at DESC;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id, "$user_ids": chunk},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                worker_user_id = _norm_text(getattr(row, "worker_user_id", None))
                if not worker_user_id or worker_user_id in out:
                    continue
                percent_snapshot = getattr(row, "percent_snapshot", None)
                try:
                    percent_snapshot = float(percent_snapshot or 0.0)
                except Exception:
                    percent_snapshot = 0.0
                out[worker_user_id] = {
                    "dispatcher_id": _norm_text(getattr(row, "dispatcher_id", None)) or None,
                    "percent_snapshot": percent_snapshot,
                    "attribution_type": _norm_text(getattr(row, "attribution_type", None)).lower() or None,
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }

        firms_pool.retry_operation_sync(_tx)

    return out


def _parse_history_period(body: dict) -> Tuple[Optional[datetime], Optional[datetime], Optional[str], Optional[str], Optional[str]]:
    raw_date = body.get("date")
    if isinstance(raw_date, str) and raw_date.strip():
        try:
            day = date.fromisoformat(raw_date.strip())
        except Exception:
            return None, None, None, None, "date must be a valid ISO date (YYYY-MM-DD)"
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        return start, start + timedelta(days=1), "day", day.isoformat(), None

    year = _safe_int(body.get("year"))
    month = _safe_int(body.get("month"))
    if year is None or year < 2020 or year > 2100:
        return None, None, None, None, "year must be an integer between 2020 and 2100"
    if month is None or month < 1 or month > 12:
        return None, None, None, None, "month must be an integer between 1 and 12"

    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end, "month", None, None


def _event_created_at(item: Dict[str, Any]) -> datetime:
    value = item.get("created_at")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _event_sort_key(item: Dict[str, Any]) -> Tuple[datetime, str]:
    return (_event_created_at(item), _norm_text(item.get("event_id")))


def _sum_amounts(events: List[Dict[str, Any]]) -> int:
    total = 0
    for item in events:
        amount_kopeks = item.get("amount_kopeks")
        if isinstance(amount_kopeks, int):
            total += abs(amount_kopeks)
    return total


def _latest_event_of_type(events: List[Dict[str, Any]], event_type_upper: str) -> Optional[Dict[str, Any]]:
    latest: Optional[Dict[str, Any]] = None
    for item in events:
        if _norm_text(item.get("event_type_upper")) != event_type_upper:
            continue
        if latest is None or _event_sort_key(item) > _event_sort_key(latest):
            latest = item
    return latest


def _extract_accrual_link(event: Optional[Dict[str, Any]]) -> str:
    if not isinstance(event, dict):
        return ""
    state = event.get("state")
    if not isinstance(state, dict):
        return ""
    return _norm_text(state.get("accrual_event_id"))


def _build_queue_worker_item(
    *,
    firm_id: str,
    employee: Dict[str, Any],
    all_events: List[Dict[str, Any]],
    salary_snapshot: List[Dict[str, Any]],
    dispatcher_attribution: Dict[str, Any],
    as_of: datetime,
) -> Dict[str, Any]:
    user_id = _norm_text(employee.get("user_id"))
    user_name = _norm_text(employee.get("user_name")) or None
    role_type = _norm_text(employee.get("role_type")).lower() or None
    dispatcher_percent_snapshot = dispatcher_attribution.get("percent_snapshot", 0.0)

    last_accrual = _latest_event_of_type(all_events, "ACCRUAL")
    period_started_at = _to_iso_utc(last_accrual.get("created_at")) if isinstance(last_accrual, dict) else None
    lower_bound = _event_created_at(last_accrual) if isinstance(last_accrual, dict) else None

    pending_events: List[Dict[str, Any]] = []
    for item in all_events:
        if _norm_text(item.get("event_type_upper")) not in CURRENT_SOURCE_EVENT_TYPES:
            continue
        if lower_bound is not None and _event_created_at(item) <= lower_bound:
            continue
        pending_events.append(item)

    pending_events.sort(key=_event_sort_key, reverse=True)

    fines = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "FINE"]
    rewards = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "REWARD"]
    shifts = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "SHIFT_END"]
    deals = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "DEAL_COMPLETE"]
    withholds: List[Dict[str, Any]] = []

    salary_paid_by_id: Dict[str, int] = {}
    rewards_fines_paid_kopeks = 0
    for item in all_events:
        if _norm_text(item.get("event_type_upper")) != "CASH":
            continue
        if lower_bound is not None and _event_created_at(item) <= lower_bound:
            continue
        state = item.get("state") if isinstance(item.get("state"), dict) else {}
        amount_kopeks = item.get("amount_kopeks")
        rewards_fines_paid_kopeks += _extract_cash_rewards_fines_paid_kopeks(
            state,
            amount_kopeks if isinstance(amount_kopeks, int) else None,
        )
        for salary_item in _extract_cash_salary_payment_items(state):
            salary_id = _norm_text(salary_item.get("salary_id"))
            salary_paid = _safe_int(salary_item.get("amount_kopeks"), 0) or 0
            if not salary_id or salary_paid <= 0:
                continue
            salary_paid_by_id[salary_id] = salary_paid_by_id.get(salary_id, 0) + salary_paid

    payable_salary_snapshot: List[Dict[str, Any]] = []
    salary_total_kopeks = 0
    for salary_item in salary_snapshot:
        if not isinstance(salary_item, dict):
            continue
        normalized_item = dict(salary_item)
        salary_id = _norm_text(normalized_item.get("salary_id"))
        source_amount_kopeks = max(_safe_int(normalized_item.get("amount_kopeks"), 0) or 0, 0)
        paid_kopeks = max(salary_paid_by_id.get(salary_id, 0), 0)
        remaining_kopeks = max(source_amount_kopeks - paid_kopeks, 0)
        overpaid_kopeks = max(paid_kopeks - source_amount_kopeks, 0)
        normalized_item["source_amount_kopeks"] = source_amount_kopeks
        normalized_item["paid_kopeks"] = paid_kopeks
        normalized_item["remaining_kopeks"] = remaining_kopeks
        normalized_item["overpaid_kopeks"] = overpaid_kopeks
        normalized_item["amount_kopeks"] = remaining_kopeks
        payable_salary_snapshot.append(normalized_item)
        salary_total_kopeks += remaining_kopeks

    rewards_total_kopeks = _sum_amounts(rewards)
    deals_total_kopeks = _sum_amounts(deals)
    shifts_total_kopeks = _sum_shift_amounts_after_dispatcher_withhold_from_snapshots(shifts)
    fines_total_kopeks = _sum_amounts(fines)
    withholds_total_kopeks = 0

    amount_kopeks = (
        salary_total_kopeks
        + rewards_total_kopeks
        + deals_total_kopeks
        + shifts_total_kopeks
        - fines_total_kopeks
        - rewards_fines_paid_kopeks
        - withholds_total_kopeks
    )

    deferred_state = _extract_deferred_state(
        user_events=all_events,
        last_accrual=last_accrual,
        as_of=as_of,
    )

    return {
        "firm_id": firm_id,
        "user_id": user_id,
        "user_name": user_name,
        "role_type": role_type,
        "amount_kopeks": amount_kopeks,
        "period_started_at": period_started_at,
        "period_ended_at": _to_iso_utc(as_of),
        "source_last_accrual_event_id": _norm_text(last_accrual.get("event_id")) or None if isinstance(last_accrual, dict) else None,
        "source_last_accrual_created_at": period_started_at,
        "totals": {
            "salary_total_kopeks": salary_total_kopeks,
            "rewards_total_kopeks": rewards_total_kopeks,
            "deals_total_kopeks": deals_total_kopeks,
            "shifts_total_kopeks": shifts_total_kopeks,
            "fines_total_kopeks": fines_total_kopeks,
            "rewards_fines_paid_kopeks": rewards_fines_paid_kopeks,
            "withholds_total_kopeks": withholds_total_kopeks,
            "events_total_count": len(pending_events),
        },
        "dispatcher_attribution": {
            "dispatcher_id": dispatcher_attribution.get("dispatcher_id"),
            "percent_snapshot": dispatcher_attribution.get("percent_snapshot", 0.0),
            "created_at": dispatcher_attribution.get("created_at"),
            "updated_at": dispatcher_attribution.get("updated_at"),
        },
        "deferred_state": deferred_state,
        "employee_salary_snapshot": payable_salary_snapshot,
        "fines": fines,
        "rewards": rewards,
        "shifts": shifts,
        "deals": deals,
        "withholds": withholds,
    }


def _normalize_percent_snapshot(value: Any) -> Decimal:
    try:
        percent = Decimal(str(value if value is not None else 0))
    except Exception:
        return Decimal("0")
    if percent < 0:
        return Decimal("0")
    if percent > 100:
        return Decimal("100")
    return percent


def _calculate_dispatcher_withhold_kopeks(amount_kopeks: int, percent_snapshot: Any) -> int:
    normalized_amount = abs(int(amount_kopeks or 0))
    if normalized_amount <= 0:
        return 0
    percent = _normalize_percent_snapshot(percent_snapshot)
    if percent <= 0:
        return 0
    result = (
        (Decimal(normalized_amount) * percent / Decimal("100"))
        .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )
    return int(result)


def _sum_amounts_after_dispatcher_withhold(
    events: List[Dict[str, Any]],
    *,
    percent_snapshot: Any,
) -> int:
    total = 0
    for item in events:
        amount_kopeks = item.get("amount_kopeks")
        if not isinstance(amount_kopeks, int):
            continue
        gross_amount_kopeks = abs(amount_kopeks)
        dispatcher_withhold_kopeks = _calculate_dispatcher_withhold_kopeks(
            gross_amount_kopeks,
            percent_snapshot,
        )
        total += max(gross_amount_kopeks - dispatcher_withhold_kopeks, 0)
    return total


def _sum_shift_amounts_after_dispatcher_withhold_from_snapshots(
    events: List[Dict[str, Any]],
) -> int:
    total = 0
    for item in events:
        amount_kopeks = item.get("amount_kopeks")
        if not isinstance(amount_kopeks, int):
            continue
        work_item_assign = item.get("work_item_assign")
        dispatcher_attribution = (
            work_item_assign.get("dispatcher_attribution")
            if isinstance(work_item_assign, dict)
            and isinstance(work_item_assign.get("dispatcher_attribution"), dict)
            else {}
        )
        percent_snapshot = float(dispatcher_attribution.get("percent_snapshot", 0.0) or 0.0)
        gross_amount_kopeks = abs(amount_kopeks)
        dispatcher_withhold_kopeks = _calculate_dispatcher_withhold_kopeks(
            gross_amount_kopeks,
            percent_snapshot,
        )
        total += max(gross_amount_kopeks - dispatcher_withhold_kopeks, 0)
    return total


def _dispatcher_scope_key(
    *,
    attribution_type: Any,
    dispatcher_id: Any,
) -> Optional[Tuple[str, Optional[str]]]:
    normalized_type = _norm_text(attribution_type).lower()
    if normalized_type not in {"dispatcher", "nominal"}:
        return None
    normalized_dispatcher_id = _norm_text(dispatcher_id) or None
    if normalized_type == "nominal":
        normalized_dispatcher_id = None
    if normalized_type == "dispatcher" and normalized_dispatcher_id is None:
        return None
    return normalized_type, normalized_dispatcher_id


def _extract_shift_dispatcher_scope_from_event(
    event: Dict[str, Any],
) -> Optional[Tuple[str, Optional[str], float]]:
    work_item_assign = event.get("work_item_assign")
    if not isinstance(work_item_assign, dict):
        return None
    dispatcher_attribution = work_item_assign.get("dispatcher_attribution")
    if not isinstance(dispatcher_attribution, dict):
        return None
    attribution_type = _norm_text(dispatcher_attribution.get("attribution_type")).lower()
    dispatcher_id = _norm_text(dispatcher_attribution.get("dispatcher_id")) or None
    if attribution_type not in {"dispatcher", "nominal"}:
        return None
    if attribution_type == "dispatcher" and dispatcher_id is None:
        return None
    if attribution_type == "nominal":
        dispatcher_id = None
    percent_snapshot = float(dispatcher_attribution.get("percent_snapshot", 0.0) or 0.0)
    return attribution_type, dispatcher_id, percent_snapshot


def _collect_dispatcher_settlement_events_by_scope(
    *,
    event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
) -> Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]]:
    out: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]] = {}
    for row in event_rows:
        event_id = _norm_text(row.get("event_id"))
        if not event_id:
            continue
        if _norm_text(row.get("event_type")).upper() != "DISPATCHER_SETTLEMENT":
            continue
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        scope_key = _dispatcher_scope_key(
            attribution_type=state.get("attribution_type"),
            dispatcher_id=state.get("dispatcher_id"),
        )
        if scope_key is None:
            continue
        out.setdefault(scope_key, []).append(
            {
                "event_id": event_id,
                "event_type": row.get("event_type"),
                "event_type_upper": "DISPATCHER_SETTLEMENT",
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "state": state,
            }
        )

    for items in out.values():
        items.sort(key=_event_sort_key)
    return out


def _build_open_dispatcher_debts_by_scope(
    settlement_events_by_scope: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]],
) -> Dict[Tuple[str, Optional[str]], Dict[str, List[Dict[str, Any]]]]:
    out: Dict[Tuple[str, Optional[str]], Dict[str, List[Dict[str, Any]]]] = {}

    for scope_key, settlement_events in settlement_events_by_scope.items():
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        last_event = settlement_events[-1] if settlement_events else None
        if not isinstance(last_event, dict):
            out[scope_key] = grouped
            continue
        event_id = _norm_text(last_event.get("event_id"))
        state = last_event.get("state") if isinstance(last_event.get("state"), dict) else {}
        workers = state.get("workers") if isinstance(state.get("workers"), list) else []
        for worker in workers:
            if not isinstance(worker, dict):
                continue
            worker_user_id = _norm_text(worker.get("worker_user_id"))
            if not worker_user_id:
                continue
            carried: List[Dict[str, Any]] = []
            closure_by_source: Dict[str, int] = {}
            for closure in worker.get("debt_closures") or []:
                if not isinstance(closure, dict):
                    continue
                source_event_id = _norm_text(closure.get("source_settlement_event_id"))
                amount_kopeks = max(_safe_int(closure.get("amount_kopeks"), 0) or 0, 0)
                if not source_event_id or amount_kopeks <= 0:
                    continue
                closure_by_source[source_event_id] = amount_kopeks

            for debt in worker.get("previous_debts") or []:
                if not isinstance(debt, dict):
                    continue
                source_event_id = _norm_text(debt.get("source_settlement_event_id"))
                remaining_kopeks = max(_safe_int(debt.get("remaining_kopeks"), 0) or 0, 0)
                remaining_kopeks = max(remaining_kopeks - closure_by_source.get(source_event_id, 0), 0)
                if not source_event_id or remaining_kopeks <= 0:
                    continue
                carried.append(
                    {
                        "worker_user_id": worker_user_id,
                        "source_settlement_event_id": source_event_id,
                        "source_event_at": _norm_text(debt.get("source_event_at")) or None,
                        "source_created_at": _norm_text(debt.get("source_created_at")) or None,
                        "remaining_kopeks": remaining_kopeks,
                    }
                )

            current_period_due_kopeks = max(_safe_int(worker.get("current_period_due_kopeks"), 0) or 0, 0)
            current_period_paid_kopeks = max(_safe_int(worker.get("current_period_paid_kopeks"), 0) or 0, 0)
            current_period_remaining_kopeks = max(current_period_due_kopeks - current_period_paid_kopeks, 0)
            if current_period_remaining_kopeks > 0 and event_id:
                carried.append(
                    {
                        "worker_user_id": worker_user_id,
                        "source_settlement_event_id": event_id,
                        "source_event_at": _norm_text(state.get("event_at")) or None,
                        "source_created_at": _to_iso_utc(last_event.get("created_at")),
                        "remaining_kopeks": current_period_remaining_kopeks,
                    }
                )
            if carried:
                grouped[worker_user_id] = carried

        for worker_items in grouped.values():
            worker_items.sort(
                key=lambda item: (
                    _norm_text(item.get("source_created_at")),
                    _norm_text(item.get("source_settlement_event_id")),
                )
            )
        out[scope_key] = grouped

    return out


def _build_dispatcher_settlement_summary_for_scope(
    *,
    user_id: str,
    all_events: List[Dict[str, Any]],
    scope_key: Tuple[str, Optional[str]],
    settlement_events_by_scope: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]],
    open_dispatcher_debts_by_scope: Dict[Tuple[str, Optional[str]], Dict[str, List[Dict[str, Any]]]],
    as_of: datetime,
) -> Dict[str, Any]:
    scope_events = settlement_events_by_scope.get(scope_key) or []
    last_scope_event = scope_events[-1] if scope_events else None
    lower_bound = _event_created_at(last_scope_event) if isinstance(last_scope_event, dict) else None
    previous_debts = list((open_dispatcher_debts_by_scope.get(scope_key) or {}).get(user_id) or [])
    previous_debt_kopeks = sum(
        max(_safe_int(item.get("remaining_kopeks"), 0) or 0, 0)
        for item in previous_debts
    )

    current_period_due_kopeks = 0
    shifts_count = 0
    last_shift_percent_snapshot = 0.0
    last_activity_at = _event_created_at(last_scope_event) if isinstance(last_scope_event, dict) else datetime(1970, 1, 1, tzinfo=timezone.utc)
    for event in all_events:
        if _norm_text(event.get("event_type_upper")) != "SHIFT_END":
            continue
        if lower_bound is not None and _event_created_at(event) <= lower_bound:
            continue
        amount_kopeks = event.get("amount_kopeks")
        if not isinstance(amount_kopeks, int):
            continue
        shift_scope = _extract_shift_dispatcher_scope_from_event(event)
        if shift_scope is None:
            continue
        shift_scope_key = (shift_scope[0], shift_scope[1])
        if shift_scope_key != scope_key:
            continue
        shifts_count += 1
        last_shift_percent_snapshot = shift_scope[2]
        event_created_at = _event_created_at(event)
        if event_created_at > last_activity_at:
            last_activity_at = event_created_at
        current_period_due_kopeks += _calculate_dispatcher_withhold_kopeks(
            abs(amount_kopeks),
            shift_scope[2],
        )

    return {
        "dispatcher_id": scope_key[1],
        "attribution_type": scope_key[0],
        "percent_snapshot": last_shift_percent_snapshot,
        "period_started_at": _to_iso_utc(lower_bound) if lower_bound else None,
        "period_ended_at": _to_iso_utc(as_of),
        "source_last_settlement_event_id": _norm_text((last_scope_event or {}).get("event_id")) or None,
        "source_last_settlement_created_at": _to_iso_utc((last_scope_event or {}).get("created_at")),
        "current_period_due_kopeks": current_period_due_kopeks,
        "previous_debt_kopeks": previous_debt_kopeks,
        "amount_due_kopeks": current_period_due_kopeks + previous_debt_kopeks,
        "shifts_count": shifts_count,
        "previous_debts_count": len(previous_debts),
        "_last_activity_at": last_activity_at,
    }


def _build_dispatcher_settlement_summary_for_worker(
    *,
    user_id: str,
    all_events: List[Dict[str, Any]],
    settlement_events_by_scope: Dict[Tuple[str, Optional[str]], List[Dict[str, Any]]],
    open_dispatcher_debts_by_scope: Dict[Tuple[str, Optional[str]], Dict[str, List[Dict[str, Any]]]],
    as_of: datetime,
) -> Dict[str, Any]:
    candidate_scope_keys: set[Tuple[str, Optional[str]]] = set()
    for scope_key, debts_by_user in open_dispatcher_debts_by_scope.items():
        if debts_by_user.get(user_id):
            candidate_scope_keys.add(scope_key)
    for event in all_events:
        if _norm_text(event.get("event_type_upper")) != "SHIFT_END":
            continue
        shift_scope = _extract_shift_dispatcher_scope_from_event(event)
        if shift_scope is None:
            continue
        candidate_scope_keys.add((shift_scope[0], shift_scope[1]))

    if not candidate_scope_keys:
        return {
            "dispatcher_id": None,
            "attribution_type": None,
            "percent_snapshot": 0.0,
            "period_started_at": None,
            "period_ended_at": _to_iso_utc(as_of),
            "source_last_settlement_event_id": None,
            "source_last_settlement_created_at": None,
            "current_period_due_kopeks": 0,
            "previous_debt_kopeks": 0,
            "amount_due_kopeks": 0,
            "shifts_count": 0,
            "previous_debts_count": 0,
        }

    best_summary: Optional[Dict[str, Any]] = None
    best_activity_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for scope_key in candidate_scope_keys:
        summary = _build_dispatcher_settlement_summary_for_scope(
            user_id=user_id,
            all_events=all_events,
            scope_key=scope_key,
            settlement_events_by_scope=settlement_events_by_scope,
            open_dispatcher_debts_by_scope=open_dispatcher_debts_by_scope,
            as_of=as_of,
        )
        activity_at = summary.get("_last_activity_at")
        if not isinstance(activity_at, datetime):
            activity_at = datetime(1970, 1, 1, tzinfo=timezone.utc)
        if (_safe_int(summary.get("amount_due_kopeks"), 0) or 0) <= 0:
            continue
        if best_summary is None or activity_at > best_activity_at:
            best_summary = summary
            best_activity_at = activity_at

    if best_summary is None:
        return {
            "dispatcher_id": None,
            "attribution_type": None,
            "percent_snapshot": 0.0,
            "period_started_at": None,
            "period_ended_at": _to_iso_utc(as_of),
            "source_last_settlement_event_id": None,
            "source_last_settlement_created_at": None,
            "current_period_due_kopeks": 0,
            "previous_debt_kopeks": 0,
            "amount_due_kopeks": 0,
            "shifts_count": 0,
            "previous_debts_count": 0,
        }

    best_summary.pop("_last_activity_at", None)
    return best_summary


def _collect_linked_status_events(
    *,
    event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for row in event_rows:
        event_id = _norm_text(row.get("event_id"))
        if not event_id:
            continue
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        event_type = _norm_text(row.get("event_type"))
        event_type_upper = event_type.upper()
        if event_type_upper not in HISTORY_STATUS_EVENT_TYPES:
            continue
        amount_kopeks = extract_amount_kopeks(state)
        linked_accrual_id = _norm_text(state.get("accrual_event_id"))
        out.setdefault(linked_accrual_id, []).append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "event_type_upper": event_type_upper,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "state": state,
                "amount_kopeks": amount_kopeks,
            }
        )
    return out


def handle_payroll_queue(
    *,
    body: dict,
    firm_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    appeals_pool: Optional[ydb.SessionPool],
    appeals_database: Optional[str],
    firms_pool: ydb.SessionPool,
    firms_database: str,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.payroll_queue.start", firm_id=firm_id)

    page, page_size, page_error = _parse_page(body)
    if page_error:
        return bad_request(page_error)

    as_of, as_of_error = _parse_as_of(body)
    if as_of_error:
        return bad_request(as_of_error)
    if as_of is None:
        return bad_request("as_of must be a valid ISO datetime")

    filter_user_id = _norm_text(body.get("user_id")) or None

    try:
        employees = _read_payroll_employees(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            filter_user_id=filter_user_id,
        )
        if not employees:
            return ok_response(
                {
                    "firm_id": firm_id,
                    "as_of": _to_iso_utc(as_of),
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False,
                    "ordinary_count": 0,
                    "deferred_count": 0,
                    "items": [],
                }
            )

        employee_ids = [item["user_id"] for item in employees]
        names_by_user_id = _read_user_names(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=employee_ids,
        )
        dispatcher_by_user_id = _read_dispatcher_attributions(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            user_ids=employee_ids,
        )

        start_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_at = as_of + timedelta(seconds=1)
        event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start_at,
            end=end_at,
        )
        event_ids = [row["event_id"] for row in event_rows if _norm_text(row.get("event_id"))]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )
        dispatcher_settlement_events_by_scope = _collect_dispatcher_settlement_events_by_scope(
            event_rows=event_rows,
            states_by_event_id=states_by_event_id,
        )
        open_dispatcher_debts_by_scope = _build_open_dispatcher_debts_by_scope(
            dispatcher_settlement_events_by_scope,
        )

        all_worker_events: Dict[str, List[Dict[str, Any]]] = {}
        for employee in employees:
            user_id = employee["user_id"]
            employee_events = _collect_employee_events(
                event_rows=event_rows,
                states_by_event_id=states_by_event_id,
                user_id=user_id,
            )
            all_worker_events[user_id] = employee_events

        work_item_amount_context = _build_work_item_amount_context(
            events=[
                event
                for worker_events in all_worker_events.values()
                for event in worker_events
            ],
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        for user_id, worker_events in list(all_worker_events.items()):
            all_worker_events[user_id] = _enrich_work_item_amounts(
                events=worker_events,
                amount_context=work_item_amount_context,
                logger=logger,
            )

        object_ids: List[str] = []
        fine_event_ids: List[str] = []
        for worker_events in all_worker_events.values():
            for event in worker_events:
                object_id = _norm_text(event.get("object_id"))
                if object_id:
                    object_ids.append(object_id)
                if _norm_text(event.get("event_type_upper")) == "FINE":
                    event_id = _norm_text(event.get("event_id"))
                    if event_id:
                        fine_event_ids.append(event_id)

        objects_map = _read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_id,
            object_ids=object_ids,
        )
        fine_disputes_by_event_id = _read_fine_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_id,
            event_ids=fine_event_ids,
        )

        items: List[Dict[str, Any]] = []
        for employee in employees:
            user_id = employee["user_id"]
            employee["user_name"] = names_by_user_id.get(user_id) or user_id
            salary_snapshot = _read_employee_salary_snapshot(
                notices_pool=notices_pool,
                notices_database=notices_database,
                firm_id=firm_id,
                user_id=user_id,
                as_of=as_of,
            )
            all_events = all_worker_events.get(user_id, [])
            queue_item = _build_current_finance_snapshot(
                firm_id=firm_id,
                user_id=user_id,
                user_name=employee.get("user_name"),
                role_type=employee.get("role_type"),
                all_events=all_events,
                salary_snapshot=salary_snapshot,
                dispatcher_attribution=dispatcher_by_user_id.get(user_id) or {},
                as_of=as_of,
            )
            queue_item["dispatcher_settlement"] = _build_dispatcher_settlement_summary_for_worker(
                user_id=user_id,
                all_events=all_events,
                settlement_events_by_scope=dispatcher_settlement_events_by_scope,
                open_dispatcher_debts_by_scope=open_dispatcher_debts_by_scope,
                as_of=as_of,
            )
            queue_item["fines"] = _build_response_events(
                events=queue_item["fines"],
                objects_map=objects_map,
                fine_disputes_by_event_id=fine_disputes_by_event_id,
            )
            queue_item["rewards"] = _build_response_events(
                events=queue_item["rewards"],
                objects_map=objects_map,
                fine_disputes_by_event_id={},
            )
            queue_item["cash"] = _build_response_events(
                events=queue_item.get("cash", []),
                objects_map=objects_map,
                fine_disputes_by_event_id={},
            )
            queue_item["shifts"] = _build_response_events(
                events=queue_item["shifts"],
                objects_map=objects_map,
                fine_disputes_by_event_id={},
            )
            queue_item["deals"] = _build_response_events(
                events=queue_item["deals"],
                objects_map=objects_map,
                fine_disputes_by_event_id={},
            )
            queue_item["withholds"] = _build_response_events(
                events=queue_item["withholds"],
                objects_map=objects_map,
                fine_disputes_by_event_id={},
            )
            items.append(queue_item)

        items.sort(
            key=lambda item: (
                0 if item.get("deferred_state", {}).get("is_deferred") else 1,
                -(_safe_int(item.get("amount_kopeks"), 0) or 0),
                _norm_text(item.get("user_name")),
                _norm_text(item.get("user_id")),
            )
        )

        total = len(items)
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total)
        page_items = items[start_idx:end_idx] if start_idx < total else []
        deferred_count = sum(1 for item in items if item.get("deferred_state", {}).get("is_deferred") is True)
        ordinary_count = total - deferred_count

        logger.info(
            "analytics_getter.payroll_queue.success",
            firm_id=firm_id,
            total=total,
            deferred_count=deferred_count,
            page=page,
            page_size=page_size,
            page_items=len(page_items),
        )

        return ok_response(
            {
                "firm_id": firm_id,
                "as_of": _to_iso_utc(as_of),
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
                "has_next": end_idx < total,
                "has_prev": page > 0 and total > 0,
                "ordinary_count": ordinary_count,
                "deferred_count": deferred_count,
                "items": page_items,
            }
        )
    except Exception as e:
        logger.error("analytics_getter.payroll_queue.error", error=str(e))
        hlog.exception("analytics_getter.payroll_queue.error", error=str(e))
        return server_error("Internal Server Error")


def handle_payroll_history(
    *,
    body: dict,
    firm_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.payroll_history.start", firm_id=firm_id)

    page, page_size, page_error = _parse_page(body)
    if page_error:
        return bad_request(page_error)

    start_at, end_at, mode, selected_date, period_error = _parse_history_period(body)
    if period_error:
        return bad_request(period_error)
    if start_at is None or end_at is None or mode is None:
        return bad_request("history period is required")

    try:
        accrual_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start_at,
            end=end_at,
            event_types_sql="'accrual', 'ACCRUAL'",
        )
        accrual_ids = [row["event_id"] for row in accrual_rows if _norm_text(row.get("event_id"))]
        accrual_states = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=accrual_ids,
            logger=logger,
        )

        if not accrual_rows:
            return ok_response(
                {
                    "firm_id": firm_id,
                    "mode": mode,
                    "selected_date": selected_date,
                    "period_started_at": _to_iso_utc(start_at),
                    "period_ended_at": _to_iso_utc(end_at),
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False,
                    "items": [],
                }
            )

        history_status_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start_at,
            end=datetime.now(timezone.utc) + timedelta(seconds=1),
            event_types_sql="'cash', 'CASH'",
        )
        history_status_ids = [row["event_id"] for row in history_status_rows if _norm_text(row.get("event_id"))]
        status_states = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=history_status_ids,
            logger=logger,
        )
        linked_status_by_accrual_id = _collect_linked_status_events(
            event_rows=history_status_rows,
            states_by_event_id=status_states,
        )

        user_ids: List[str] = []
        for event_id in accrual_ids:
            state = accrual_states.get(event_id)
            if not isinstance(state, dict):
                continue
            user_id = _norm_text(extract_user_id(state))
            if user_id:
                user_ids.append(user_id)
        names_by_user_id = _read_user_names(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=user_ids,
        )

        items: List[Dict[str, Any]] = []
        for row in accrual_rows:
            accrual_event_id = _norm_text(row.get("event_id"))
            if not accrual_event_id:
                continue
            state = accrual_states.get(accrual_event_id)
            if not isinstance(state, dict):
                continue

            user_id = _norm_text(extract_user_id(state))
            user_name = _norm_text(state.get("user_name")) or names_by_user_id.get(user_id) or user_id
            linked_items = linked_status_by_accrual_id.get(accrual_event_id, [])
            latest_cash = _latest_event_of_type(linked_items, "CASH")

            status = "accrued"
            paid_at = None
            status_event_id = None
            if latest_cash is not None:
                status = "paid"
                paid_at = _to_iso_utc(latest_cash.get("created_at"))
                status_event_id = _norm_text(latest_cash.get("event_id")) or None

            if mode == "month" and status != "paid":
                continue

            items.append(
                {
                    "accrual_event_id": accrual_event_id,
                    "status": status,
                    "status_event_id": status_event_id,
                    "user_id": user_id,
                    "user_name": user_name,
                    "amount_kopeks": _safe_int(state.get("amount_kopeks"), 0) or 0,
                    "event_at": _norm_text(state.get("event_at")) or _to_iso_utc(row.get("created_at")),
                    "paid_at": paid_at,
                    "deferred_until": None,
                    "accrual_snapshot": state,
                }
            )

        items.sort(
            key=lambda item: (
                item.get("event_at") or "",
                _norm_text(item.get("accrual_event_id")),
            ),
            reverse=True,
        )

        total = len(items)
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total)
        page_items = items[start_idx:end_idx] if start_idx < total else []

        logger.info(
            "analytics_getter.payroll_history.success",
            firm_id=firm_id,
            mode=mode,
            total=total,
            page=page,
            page_size=page_size,
            page_items=len(page_items),
        )

        return ok_response(
            {
                "firm_id": firm_id,
                "mode": mode,
                "selected_date": selected_date,
                "period_started_at": _to_iso_utc(start_at),
                "period_ended_at": _to_iso_utc(end_at),
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
                "has_next": end_idx < total,
                "has_prev": page > 0 and total > 0,
                "items": page_items,
            }
        )
    except Exception as e:
        logger.error("analytics_getter.payroll_history.error", error=str(e))
        hlog.exception("analytics_getter.payroll_history.error", error=str(e))
        return server_error("Internal Server Error")
