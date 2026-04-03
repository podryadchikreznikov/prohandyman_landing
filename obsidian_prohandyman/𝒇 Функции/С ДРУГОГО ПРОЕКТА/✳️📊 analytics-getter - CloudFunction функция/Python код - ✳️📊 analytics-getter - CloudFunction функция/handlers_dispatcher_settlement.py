# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Set, Tuple

import ydb

from utils import bad_request, ok_response, server_error

from event_state import fetch_firm_event_states
from handlers_employee_finance import (
    _build_work_item_amount_context,
    _collect_employee_events,
    _enrich_work_item_amounts,
    _event_created_at,
    _event_sort_key,
    _norm_text,
    _parse_as_of,
    _parse_page,
    _read_finance_event_rows,
    _read_objects_by_ids,
    _safe_int,
    _to_iso_utc,
)
from handlers_payroll import _read_user_names


EVENT_TYPE_SHIFT_END = "SHIFT_END"
EVENT_TYPE_DISPATCHER_SETTLEMENT = "DISPATCHER_SETTLEMENT"


def _parse_scope(body: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    attribution_type = _norm_text(body.get("attribution_type")).lower()
    if attribution_type not in {"dispatcher", "nominal"}:
        return None, None, "attribution_type must be one of: dispatcher, nominal"

    dispatcher_id = _norm_text(body.get("dispatcher_id")) or None
    if attribution_type == "dispatcher" and dispatcher_id is None:
        return None, None, "dispatcher_id is required for attribution_type=dispatcher"
    if attribution_type == "nominal" and dispatcher_id is not None:
        return None, None, "dispatcher_id must be omitted for attribution_type=nominal"

    return attribution_type, dispatcher_id, None


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


def _calculate_dispatcher_withheld_kopeks(amount_kopeks: int, percent_snapshot: Any) -> int:
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


def _read_effective_dispatcher_attributions(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        SELECT worker_user_id, dispatcher_id, percent_snapshot, attribution_type, created_at, updated_at
        FROM dispatcher_attributions
        WHERE firm_id = $firm_id
        ORDER BY
            worker_user_id ASC,
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
            {"$firm_id": firm_id},
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
                "worker_user_id": worker_user_id,
                "dispatcher_id": _norm_text(getattr(row, "dispatcher_id", None)) or None,
                "attribution_type": _norm_text(getattr(row, "attribution_type", None)).lower() or None,
                "percent_snapshot": percent_snapshot,
                "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
            }

    firms_pool.retry_operation_sync(_tx)
    return out


def _scope_matches(
    attribution: Optional[Dict[str, Any]],
    *,
    attribution_type: str,
    dispatcher_id: Optional[str],
) -> bool:
    if not isinstance(attribution, dict):
        return False
    if _norm_text(attribution.get("attribution_type")).lower() != attribution_type:
        return False
    current_dispatcher_id = _norm_text(attribution.get("dispatcher_id")) or None
    if attribution_type == "dispatcher":
        return current_dispatcher_id == dispatcher_id
    return current_dispatcher_id is None


def _collect_dispatcher_settlement_events(
    *,
    event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
    attribution_type: str,
    dispatcher_id: Optional[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in event_rows:
        event_id = _norm_text(row.get("event_id"))
        if not event_id:
            continue
        event_type_upper = _norm_text(row.get("event_type")).upper()
        if event_type_upper != EVENT_TYPE_DISPATCHER_SETTLEMENT:
            continue
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        state_attribution_type = _norm_text(state.get("attribution_type")).lower()
        state_dispatcher_id = _norm_text(state.get("dispatcher_id")) or None
        if state_attribution_type != attribution_type:
            continue
        if attribution_type == "dispatcher" and state_dispatcher_id != dispatcher_id:
            continue
        if attribution_type == "nominal" and state_dispatcher_id is not None:
            continue
        out.append(
            {
                "event_id": event_id,
                "event_type": row.get("event_type"),
                "event_type_upper": event_type_upper,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "state": state,
            }
        )
    out.sort(key=_event_sort_key)
    return out


def _build_open_debts_by_worker(
    settlement_events: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    last_event = settlement_events[-1] if settlement_events else None
    if not isinstance(last_event, dict):
        return {}

    event_id = _norm_text(last_event.get("event_id"))
    state = last_event.get("state") if isinstance(last_event.get("state"), dict) else {}
    workers = state.get("workers") if isinstance(state.get("workers"), list) else []
    out: Dict[str, List[Dict[str, Any]]] = {}

    for worker in workers:
        if not isinstance(worker, dict):
            continue
        worker_user_id = _norm_text(worker.get("worker_user_id"))
        if not worker_user_id:
            continue

        incoming_previous_debts = worker.get("previous_debts") if isinstance(worker.get("previous_debts"), list) else []
        debt_closures = worker.get("debt_closures") if isinstance(worker.get("debt_closures"), list) else []
        closure_by_source: Dict[str, int] = {}
        for closure in debt_closures:
            if not isinstance(closure, dict):
                continue
            source_event_id = _norm_text(closure.get("source_settlement_event_id"))
            amount_kopeks = max(_safe_int(closure.get("amount_kopeks"), 0) or 0, 0)
            if not source_event_id or amount_kopeks <= 0:
                continue
            closure_by_source[source_event_id] = amount_kopeks

        carried: List[Dict[str, Any]] = []
        for debt in incoming_previous_debts:
            if not isinstance(debt, dict):
                continue
            source_event_id = _norm_text(debt.get("source_settlement_event_id"))
            if not source_event_id:
                continue
            remaining_kopeks = max(_safe_int(debt.get("remaining_kopeks"), 0) or 0, 0)
            remaining_kopeks = max(remaining_kopeks - closure_by_source.get(source_event_id, 0), 0)
            if remaining_kopeks <= 0:
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
            carried.sort(
                key=lambda item: (
                    _norm_text(item.get("source_created_at")),
                    _norm_text(item.get("source_settlement_event_id")),
                )
            )
            out[worker_user_id] = carried

    return out


def _extract_dispatcher_snapshot_from_shift_event(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    work_item_assign = event.get("work_item_assign")
    if not isinstance(work_item_assign, dict):
        return None
    dispatcher_attribution = work_item_assign.get("dispatcher_attribution")
    if not isinstance(dispatcher_attribution, dict):
        return None
    attribution_type = _norm_text(dispatcher_attribution.get("attribution_type")).lower()
    if attribution_type not in {"dispatcher", "nominal"}:
        return None
    dispatcher_id = _norm_text(dispatcher_attribution.get("dispatcher_id")) or None
    if attribution_type == "dispatcher" and dispatcher_id is None:
        return None
    if attribution_type == "nominal":
        dispatcher_id = None
    return {
        "dispatcher_id": dispatcher_id,
        "dispatcher_name": _norm_text(dispatcher_attribution.get("dispatcher_name")) or None,
        "attribution_type": attribution_type,
        "percent_snapshot": float(dispatcher_attribution.get("percent_snapshot") or 0.0),
        "created_at": _norm_text(dispatcher_attribution.get("created_at")) or None,
        "updated_at": _norm_text(dispatcher_attribution.get("updated_at")) or None,
    }


def _shift_snapshot_matches_scope(
    snapshot: Optional[Dict[str, Any]],
    *,
    attribution_type: str,
    dispatcher_id: Optional[str],
) -> bool:
    if not isinstance(snapshot, dict):
        return False
    if _norm_text(snapshot.get("attribution_type")).lower() != attribution_type:
        return False
    snapshot_dispatcher_id = _norm_text(snapshot.get("dispatcher_id")) or None
    if attribution_type == "dispatcher":
        return snapshot_dispatcher_id == dispatcher_id
    return snapshot_dispatcher_id is None


def handle_dispatcher_settlement_queue(
    *,
    body: dict,
    firm_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.dispatcher_settlement_queue.start", firm_id=firm_id)

    page, page_size, page_error = _parse_page(body)
    if page_error:
        return bad_request(page_error)

    as_of, as_of_error = _parse_as_of(body)
    if as_of_error:
        return bad_request(as_of_error)
    if as_of is None:
        return bad_request("as_of must be a valid ISO datetime")

    attribution_type, dispatcher_id, scope_error = _parse_scope(body)
    if scope_error:
        return bad_request(scope_error)

    try:
        start_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end_at = as_of + timedelta(seconds=1)
        event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start_at,
            end=end_at,
            event_types_sql="'shift_end', 'SHIFT_END', 'dispatcher_settlement', 'DISPATCHER_SETTLEMENT'",
        )
        event_ids = [row["event_id"] for row in event_rows if _norm_text(row.get("event_id"))]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )

        settlement_events = _collect_dispatcher_settlement_events(
            event_rows=event_rows,
            states_by_event_id=states_by_event_id,
            attribution_type=attribution_type or "",
            dispatcher_id=dispatcher_id,
        )
        last_settlement = settlement_events[-1] if settlement_events else None
        lower_bound = _event_created_at(last_settlement) if isinstance(last_settlement, dict) else None
        open_debts_by_worker = _build_open_debts_by_worker(settlement_events)
        relevant_worker_ids: Set[str] = set(open_debts_by_worker.keys())
        for row in event_rows:
            event_id = _norm_text(row.get("event_id"))
            if not event_id or _norm_text(row.get("event_type")).upper() != EVENT_TYPE_SHIFT_END:
                continue
            state = states_by_event_id.get(event_id)
            if not isinstance(state, dict):
                continue
            worker_user_id = _norm_text(state.get("worker_id"))
            if not worker_user_id:
                continue
            created_at = _event_created_at(
                {
                    "event_id": event_id,
                    "created_at": row.get("created_at"),
                }
            )
            if lower_bound is not None and created_at <= lower_bound:
                continue
            relevant_worker_ids.add(worker_user_id)
        relevant_worker_ids = sorted(relevant_worker_ids)

        if not relevant_worker_ids:
            return ok_response(
                {
                    "firm_id": firm_id,
                    "dispatcher_id": dispatcher_id,
                    "dispatcher_name": None,
                    "attribution_type": attribution_type,
                    "as_of": _to_iso_utc(as_of),
                    "period_started_at": _to_iso_utc(lower_bound) if lower_bound else None,
                    "period_ended_at": _to_iso_utc(as_of),
                    "source_last_settlement_event_id": _norm_text((last_settlement or {}).get("event_id")) or None,
                    "source_last_settlement_created_at": _to_iso_utc((last_settlement or {}).get("created_at")),
                    "page": page,
                    "page_size": page_size,
                    "total": 0,
                    "total_pages": 1,
                    "has_next": False,
                    "has_prev": False,
                    "totals": {
                        "current_period_due_kopeks": 0,
                        "previous_debt_kopeks": 0,
                        "amount_due_kopeks": 0,
                        "workers_count": 0,
                        "shifts_count": 0,
                    },
                    "items": [],
                }
            )

        user_names = _read_user_names(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=relevant_worker_ids + ([dispatcher_id] if dispatcher_id else []),
        )
        dispatcher_name = user_names.get(dispatcher_id) if dispatcher_id else None

        object_ids: List[str] = []
        items: List[Dict[str, Any]] = []
        last_settlement_worker_by_id = {
            _norm_text(worker.get("worker_user_id")): worker
            for worker in ((last_settlement or {}).get("state") or {}).get("workers", [])
            if isinstance(worker, dict) and _norm_text(worker.get("worker_user_id"))
        }
        for worker_user_id in relevant_worker_ids:
            worker_events = _collect_employee_events(
                event_rows=event_rows,
                states_by_event_id=states_by_event_id,
                user_id=worker_user_id,
            )
            amount_context = _build_work_item_amount_context(
                events=worker_events,
                firm_id=firm_id,
                objects_pool=objects_pool,
                objects_database=objects_database,
                events_pool=events_pool,
                events_database=events_database,
                meta_pool=meta_pool,
                meta_database=meta_database,
                logger=logger,
            )
            worker_events = _enrich_work_item_amounts(
                events=worker_events,
                amount_context=amount_context,
                logger=logger,
            )
            shifts: List[Dict[str, Any]] = []
            for event in worker_events:
                if _norm_text(event.get("event_type_upper")) != EVENT_TYPE_SHIFT_END:
                    continue
                if lower_bound is not None and _event_created_at(event) <= lower_bound:
                    continue
                amount_kopeks = event.get("amount_kopeks")
                if not isinstance(amount_kopeks, int):
                    continue
                snapshot = _extract_dispatcher_snapshot_from_shift_event(event)
                if not _shift_snapshot_matches_scope(
                    snapshot,
                    attribution_type=attribution_type or "",
                    dispatcher_id=dispatcher_id,
                ):
                    continue
                state = event.get("state") if isinstance(event.get("state"), dict) else {}
                object_id = _norm_text(event.get("object_id")) or None
                if object_id:
                    object_ids.append(object_id)
                gross_amount_kopeks = abs(amount_kopeks)
                percent_snapshot = float((snapshot or {}).get("percent_snapshot") or 0.0)
                shifts.append(
                    {
                        "shift_event_id": _norm_text(event.get("event_id")),
                        "shift_id": _norm_text(state.get("shift_id")) or None,
                        "object_id": object_id,
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

            previous_debts = list(open_debts_by_worker.get(worker_user_id) or [])
            current_period_due_kopeks = sum(
                max(_safe_int(item.get("withheld_amount_kopeks"), 0) or 0, 0)
                for item in shifts
            )
            previous_debt_kopeks = sum(
                max(_safe_int(item.get("remaining_kopeks"), 0) or 0, 0)
                for item in previous_debts
            )
            amount_due_kopeks = current_period_due_kopeks + previous_debt_kopeks
            if amount_due_kopeks <= 0:
                continue

            percent_snapshot = 0.0
            if shifts:
                percent_snapshot = float(shifts[-1].get("percent_snapshot") or 0.0)
            elif isinstance(last_settlement_worker_by_id.get(worker_user_id), dict):
                percent_snapshot = float(
                    last_settlement_worker_by_id[worker_user_id].get("percent_snapshot") or 0.0
                )

            items.append(
                {
                    "worker_user_id": worker_user_id,
                    "worker_name": user_names.get(worker_user_id) or worker_user_id,
                    "dispatcher_id": dispatcher_id if attribution_type == "dispatcher" else None,
                    "dispatcher_name": dispatcher_name if attribution_type == "dispatcher" else None,
                    "attribution_type": attribution_type,
                    "percent_snapshot": percent_snapshot,
                    "current_period_due_kopeks": current_period_due_kopeks,
                    "previous_debt_kopeks": previous_debt_kopeks,
                    "amount_due_kopeks": amount_due_kopeks,
                    "shifts": shifts,
                    "previous_debts": previous_debts,
                }
            )

        objects_map = _read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_id,
            object_ids=object_ids,
        )
        for item in items:
            shifts = item.get("shifts") if isinstance(item.get("shifts"), list) else []
            for shift in shifts:
                if not isinstance(shift, dict):
                    continue
                object_id = _norm_text(shift.get("object_id"))
                object_info = objects_map.get(object_id) if object_id else None
                shift["object_name"] = _norm_text((object_info or {}).get("object_name")) or None

        items.sort(
            key=lambda item: (
                -(_safe_int(item.get("amount_due_kopeks"), 0) or 0),
                _norm_text(item.get("worker_name")),
                _norm_text(item.get("worker_user_id")),
            )
        )

        total = len(items)
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total)
        page_items = items[start_idx:end_idx] if start_idx < total else []

        totals = {
            "current_period_due_kopeks": sum(
                max(_safe_int(item.get("current_period_due_kopeks"), 0) or 0, 0)
                for item in items
            ),
            "previous_debt_kopeks": sum(
                max(_safe_int(item.get("previous_debt_kopeks"), 0) or 0, 0)
                for item in items
            ),
            "amount_due_kopeks": sum(
                max(_safe_int(item.get("amount_due_kopeks"), 0) or 0, 0)
                for item in items
            ),
            "workers_count": total,
            "shifts_count": sum(
                len(item.get("shifts") or [])
                for item in items
                if isinstance(item.get("shifts"), list)
            ),
        }

        logger.info(
            "analytics_getter.dispatcher_settlement_queue.success",
            firm_id=firm_id,
            attribution_type=attribution_type,
            dispatcher_id=dispatcher_id,
            workers_count=total,
            amount_due_kopeks=totals["amount_due_kopeks"],
        )

        return ok_response(
            {
                "firm_id": firm_id,
                "dispatcher_id": dispatcher_id,
                "dispatcher_name": dispatcher_name,
                "attribution_type": attribution_type,
                "as_of": _to_iso_utc(as_of),
                "period_started_at": _to_iso_utc(lower_bound) if lower_bound else None,
                "period_ended_at": _to_iso_utc(as_of),
                "source_last_settlement_event_id": _norm_text((last_settlement or {}).get("event_id")) or None,
                "source_last_settlement_created_at": _to_iso_utc((last_settlement or {}).get("created_at")),
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
                "has_next": end_idx < total,
                "has_prev": page > 0 and total > 0,
                "totals": totals,
                "items": page_items,
            }
        )
    except Exception as e:
        logger.error("analytics_getter.dispatcher_settlement_queue.error", error=str(e))
        hlog.exception("analytics_getter.dispatcher_settlement_queue.error", error=str(e))
        return server_error("Internal Server Error")
