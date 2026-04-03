# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import ydb

from utils import JsonLogger, bad_request, created, server_error
from utils.util_log import YCLogger
from utils.util_metadata import parse_json_value

from common import is_uuid
from constants import EVENT_DISPATCHER_SETTLEMENT
from events_helper import create_event_entity
from handlers import _read_user_full_name


def _norm_text(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except Exception:
            value = str(value)
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _to_iso_utc(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _event_created_at(item: Dict[str, Any]) -> datetime:
    value = item.get("created_at")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _event_sort_key(item: Dict[str, Any]) -> Tuple[datetime, str]:
    return (_event_created_at(item), _norm_text(item.get("event_id")))


def _parse_scope(body: dict) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    attribution_type = _norm_text(body.get("attribution_type")).lower()
    if attribution_type not in {"dispatcher", "nominal"}:
        return None, None, "attribution_type must be one of: dispatcher, nominal"

    dispatcher_id = _norm_text(body.get("dispatcher_id")) or None
    if attribution_type == "dispatcher":
        if dispatcher_id is None:
            return None, None, "dispatcher_id is required for attribution_type=dispatcher"
        if not is_uuid(dispatcher_id):
            return None, None, "dispatcher_id must be a valid UUID"
    elif dispatcher_id is not None:
        return None, None, "dispatcher_id must be omitted for attribution_type=nominal"

    return attribution_type, dispatcher_id, None


def _read_dispatcher_settlement_rows(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        SELECT event_id, event_type, created_at, updated_at
        FROM finance_events
        WHERE firm_id = $firm_id
          AND event_type IN ('dispatcher_settlement', 'DISPATCHER_SETTLEMENT')
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = _norm_text(getattr(row, "event_id", None))
            if not event_id:
                continue
            out.append(
                {
                    "event_id": event_id,
                    "event_type": _norm_text(getattr(row, "event_type", None)),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return out


def _fetch_firm_event_states(
    *,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    firm_id: str,
    event_ids: List[str],
) -> Dict[str, dict]:
    if not event_ids:
        return {}

    out: Dict[str, dict] = {}

    def _chunked(values: List[str], chunk_size: int) -> List[List[str]]:
        if chunk_size <= 0:
            return [values]
        return [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]

    def _tx(session: ydb.Session, ids: List[str]):
        q = f"""
        PRAGMA TablePathPrefix('{meta_database}');
        DECLARE $ids AS List<Utf8>;
        SELECT entity_id, state_json
        FROM `aggregate_state_{firm_id}`
        WHERE entity_id IN $ids;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = _norm_text(getattr(row, "entity_id", None))
            if not event_id:
                continue
            parsed = parse_json_value(getattr(row, "state_json", None))
            if isinstance(parsed, dict):
                out[event_id] = parsed

    for chunk in _chunked(event_ids, 200):
        meta_pool.retry_operation_sync(lambda session, _ids=chunk: _tx(session, _ids))

    return out


def _collect_scope_events(
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
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "state": state,
            }
        )
    out.sort(key=_event_sort_key)
    return out


def _build_open_debts_by_worker(scope_events: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    last_event = scope_events[-1] if scope_events else None
    if not isinstance(last_event, dict):
        return {}

    event_id = _norm_text(last_event.get("event_id"))
    state = last_event.get("state") if isinstance(last_event.get("state"), dict) else {}
    workers = state.get("workers") if isinstance(state.get("workers"), list) else []
    grouped: Dict[str, Dict[str, int]] = {}

    for worker in workers:
        if not isinstance(worker, dict):
            continue
        worker_user_id = _norm_text(worker.get("worker_user_id"))
        if not worker_user_id:
            continue

        carried: Dict[str, int] = {}
        previous_debts = worker.get("previous_debts") if isinstance(worker.get("previous_debts"), list) else []
        for debt in previous_debts:
            if not isinstance(debt, dict):
                continue
            source_event_id = _norm_text(debt.get("source_settlement_event_id"))
            remaining_kopeks = max(_safe_int(debt.get("remaining_kopeks"), 0) or 0, 0)
            if not source_event_id or remaining_kopeks <= 0:
                continue
            carried[source_event_id] = remaining_kopeks

        debt_closures = worker.get("debt_closures") if isinstance(worker.get("debt_closures"), list) else []
        for closure in debt_closures:
            if not isinstance(closure, dict):
                continue
            source_event_id = _norm_text(closure.get("source_settlement_event_id"))
            amount_kopeks = max(_safe_int(closure.get("amount_kopeks"), 0) or 0, 0)
            if not source_event_id or amount_kopeks <= 0 or source_event_id not in carried:
                continue
            remaining_kopeks = max(carried[source_event_id] - amount_kopeks, 0)
            if remaining_kopeks <= 0:
                carried.pop(source_event_id, None)
            else:
                carried[source_event_id] = remaining_kopeks

        current_period_due_kopeks = max(_safe_int(worker.get("current_period_due_kopeks"), 0) or 0, 0)
        current_period_paid_kopeks = max(_safe_int(worker.get("current_period_paid_kopeks"), 0) or 0, 0)
        current_period_remaining_kopeks = max(current_period_due_kopeks - current_period_paid_kopeks, 0)
        if current_period_remaining_kopeks > 0 and event_id:
            carried[event_id] = current_period_remaining_kopeks

        if carried:
            grouped[worker_user_id] = carried
    return grouped


def _validate_worker_payload(
    *,
    worker: dict,
    attribution_type: str,
    dispatcher_id: Optional[str],
    actual_open_debts: Dict[str, int],
    seen_shift_event_ids: set[str],
) -> Optional[str]:
    worker_user_id = _norm_text(worker.get("worker_user_id"))
    worker_name = _norm_text(worker.get("worker_name"))
    if not worker_user_id:
        return "workers[].worker_user_id is required"
    if not is_uuid(worker_user_id):
        return "workers[].worker_user_id must be a valid UUID"
    if not worker_name:
        return "workers[].worker_name is required"

    worker_dispatcher_id = _norm_text(worker.get("dispatcher_id")) or None
    worker_attribution_type = _norm_text(worker.get("attribution_type")).lower()
    if worker_attribution_type != attribution_type:
        return "workers[].attribution_type must match attribution_type"
    if attribution_type == "dispatcher" and worker_dispatcher_id != dispatcher_id:
        return "workers[].dispatcher_id must match dispatcher_id"
    if attribution_type == "nominal" and worker_dispatcher_id is not None:
        return "workers[].dispatcher_id must be omitted for attribution_type=nominal"

    percent_snapshot = worker.get("percent_snapshot")
    if not isinstance(percent_snapshot, (int, float)):
        return "workers[].percent_snapshot must be a number"
    if percent_snapshot < 0 or percent_snapshot > 100:
        return "workers[].percent_snapshot must be between 0 and 100"

    current_period_due_kopeks = max(_safe_int(worker.get("current_period_due_kopeks"), 0) or 0, 0)
    current_period_paid_kopeks = max(_safe_int(worker.get("current_period_paid_kopeks"), 0) or 0, 0)
    previous_debt_kopeks = max(_safe_int(worker.get("previous_debt_kopeks"), 0) or 0, 0)
    amount_due_kopeks = max(_safe_int(worker.get("amount_due_kopeks"), 0) or 0, 0)
    amount_paid_kopeks = max(_safe_int(worker.get("amount_paid_kopeks"), 0) or 0, 0)
    amount_remaining_kopeks = max(_safe_int(worker.get("amount_remaining_kopeks"), 0) or 0, 0)

    if current_period_paid_kopeks > current_period_due_kopeks:
        return "workers[].current_period_paid_kopeks must be <= current_period_due_kopeks"

    shifts = worker.get("shifts")
    if not isinstance(shifts, list):
        return "workers[].shifts must be an array"
    shifts_withheld_kopeks = 0
    for shift in shifts:
        if not isinstance(shift, dict):
            return "workers[].shifts[] must be an object"
        shift_event_id = _norm_text(shift.get("shift_event_id"))
        if not shift_event_id:
            return "workers[].shifts[].shift_event_id is required"
        if shift_event_id in seen_shift_event_ids:
            return "workers[].shifts[].shift_event_id must be unique within request"
        seen_shift_event_ids.add(shift_event_id)
        gross_amount_kopeks = _safe_int(shift.get("gross_amount_kopeks"))
        withheld_amount_kopeks = _safe_int(shift.get("withheld_amount_kopeks"))
        if gross_amount_kopeks is None or gross_amount_kopeks < 0:
            return "workers[].shifts[].gross_amount_kopeks must be a non-negative integer"
        if withheld_amount_kopeks is None or withheld_amount_kopeks < 0:
            return "workers[].shifts[].withheld_amount_kopeks must be a non-negative integer"
        shift_attribution_type = _norm_text(shift.get("attribution_type")).lower()
        shift_dispatcher_id = _norm_text(shift.get("dispatcher_id")) or None
        shift_percent_snapshot = shift.get("percent_snapshot")
        if shift_attribution_type != attribution_type:
            return "workers[].shifts[].attribution_type must match attribution_type"
        if attribution_type == "dispatcher" and shift_dispatcher_id != dispatcher_id:
            return "workers[].shifts[].dispatcher_id must match dispatcher_id"
        if attribution_type == "nominal" and shift_dispatcher_id is not None:
            return "workers[].shifts[].dispatcher_id must be omitted for attribution_type=nominal"
        if not isinstance(shift_percent_snapshot, (int, float)):
            return "workers[].shifts[].percent_snapshot must be a number"
        if shift_percent_snapshot < 0 or shift_percent_snapshot > 100:
            return "workers[].shifts[].percent_snapshot must be between 0 and 100"
        shifts_withheld_kopeks += withheld_amount_kopeks

    if shifts_withheld_kopeks != current_period_due_kopeks:
        return "workers[].current_period_due_kopeks must match sum(workers[].shifts[].withheld_amount_kopeks)"

    previous_debts = worker.get("previous_debts")
    if not isinstance(previous_debts, list):
        return "workers[].previous_debts must be an array"
    provided_previous_debts: Dict[str, int] = {}
    for debt in previous_debts:
        if not isinstance(debt, dict):
            return "workers[].previous_debts[] must be an object"
        source_event_id = _norm_text(debt.get("source_settlement_event_id"))
        remaining_kopeks = _safe_int(debt.get("remaining_kopeks"))
        if not source_event_id:
            return "workers[].previous_debts[].source_settlement_event_id is required"
        if remaining_kopeks is None or remaining_kopeks < 0:
            return "workers[].previous_debts[].remaining_kopeks must be a non-negative integer"
        if source_event_id in provided_previous_debts:
            return "workers[].previous_debts[].source_settlement_event_id must be unique"
        provided_previous_debts[source_event_id] = remaining_kopeks

    if provided_previous_debts != actual_open_debts:
        return "workers[].previous_debts does not match current open debts"

    if sum(provided_previous_debts.values()) != previous_debt_kopeks:
        return "workers[].previous_debt_kopeks must match sum(workers[].previous_debts[].remaining_kopeks)"

    debt_closures = worker.get("debt_closures")
    if not isinstance(debt_closures, list):
        return "workers[].debt_closures must be an array"
    provided_closures: Dict[str, int] = {}
    for closure in debt_closures:
        if not isinstance(closure, dict):
            return "workers[].debt_closures[] must be an object"
        source_event_id = _norm_text(closure.get("source_settlement_event_id"))
        amount_kopeks = _safe_int(closure.get("amount_kopeks"))
        if not source_event_id:
            return "workers[].debt_closures[].source_settlement_event_id is required"
        if amount_kopeks is None or amount_kopeks < 0:
            return "workers[].debt_closures[].amount_kopeks must be a non-negative integer"
        if source_event_id in provided_closures:
            return "workers[].debt_closures[].source_settlement_event_id must be unique"
        if source_event_id not in provided_previous_debts:
            return "workers[].debt_closures[].source_settlement_event_id must exist in workers[].previous_debts"
        if amount_kopeks > provided_previous_debts[source_event_id]:
            return "workers[].debt_closures[].amount_kopeks must be <= matching previous debt remaining_kopeks"
        provided_closures[source_event_id] = amount_kopeks

    closures_total_kopeks = sum(provided_closures.values())
    if amount_due_kopeks != current_period_due_kopeks + previous_debt_kopeks:
        return "workers[].amount_due_kopeks must equal current_period_due_kopeks + previous_debt_kopeks"
    if amount_paid_kopeks != current_period_paid_kopeks + closures_total_kopeks:
        return "workers[].amount_paid_kopeks must equal current_period_paid_kopeks + sum(workers[].debt_closures[].amount_kopeks)"
    if amount_paid_kopeks > amount_due_kopeks:
        return "workers[].amount_paid_kopeks must be <= workers[].amount_due_kopeks"
    if amount_remaining_kopeks != amount_due_kopeks - amount_paid_kopeks:
        return "workers[].amount_remaining_kopeks must equal amount_due_kopeks - amount_paid_kopeks"

    return None


def handle_dispatcher_settlement_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    attribution_type, dispatcher_id, scope_error = _parse_scope(body)
    if scope_error:
        return bad_request(scope_error)

    period_ended_at = _norm_text(body.get("period_ended_at"))
    if not period_ended_at:
        return bad_request("period_ended_at is required")

    dispatcher_name = _norm_text(body.get("dispatcher_name")) or None
    if dispatcher_id and dispatcher_name is None:
        dispatcher_name = _read_user_full_name(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_id=dispatcher_id,
        )

    workers = body.get("workers")
    if not isinstance(workers, list) or not workers:
        return bad_request("workers must be a non-empty array")

    amount_due_kopeks = _safe_int(body.get("amount_due_kopeks"))
    amount_paid_kopeks = _safe_int(body.get("amount_paid_kopeks"))
    if amount_due_kopeks is None or amount_due_kopeks < 0:
        return bad_request("amount_due_kopeks must be a non-negative integer")
    if amount_paid_kopeks is None or amount_paid_kopeks <= 0:
        return bad_request("amount_paid_kopeks must be a positive integer")
    if amount_paid_kopeks > amount_due_kopeks:
        return bad_request("amount_paid_kopeks must be <= amount_due_kopeks")

    try:
        event_rows = _read_dispatcher_settlement_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
        )
        event_ids = [row["event_id"] for row in event_rows if _norm_text(row.get("event_id"))]
        states_by_event_id = _fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
        )
        scope_events = _collect_scope_events(
            event_rows=event_rows,
            states_by_event_id=states_by_event_id,
            attribution_type=attribution_type or "",
            dispatcher_id=dispatcher_id,
        )
        last_scope_event = scope_events[-1] if scope_events else None
        actual_last_event_id = _norm_text((last_scope_event or {}).get("event_id")) or None
        actual_last_created_at = _to_iso_utc((last_scope_event or {}).get("created_at"))
        requested_last_event_id = _norm_text(body.get("source_last_settlement_event_id")) or None
        requested_last_created_at = _norm_text(body.get("source_last_settlement_created_at")) or None

        if requested_last_event_id != actual_last_event_id:
            return bad_request("source_last_settlement_event_id does not match current latest dispatcher settlement")
        if requested_last_created_at != (actual_last_created_at or None):
            return bad_request("source_last_settlement_created_at does not match current latest dispatcher settlement")

        actual_open_debts_by_worker = _build_open_debts_by_worker(scope_events)

        seen_shift_event_ids: set[str] = set()
        normalized_workers: List[Dict[str, Any]] = []
        totals_current_period_due_kopeks = 0
        totals_previous_debt_kopeks = 0
        totals_amount_due_kopeks = 0
        totals_amount_paid_kopeks = 0
        totals_amount_remaining_kopeks = 0
        totals_shifts_count = 0

        for worker in workers:
            if not isinstance(worker, dict):
                return bad_request("workers[] must be an object")
            worker_user_id = _norm_text(worker.get("worker_user_id"))
            validation_error = _validate_worker_payload(
                worker=worker,
                attribution_type=attribution_type or "",
                dispatcher_id=dispatcher_id,
                actual_open_debts=actual_open_debts_by_worker.get(worker_user_id) or {},
                seen_shift_event_ids=seen_shift_event_ids,
            )
            if validation_error:
                return bad_request(validation_error)

            normalized_worker = {
                "worker_user_id": worker_user_id,
                "worker_name": _norm_text(worker.get("worker_name")),
                "dispatcher_id": dispatcher_id if attribution_type == "dispatcher" else None,
                "dispatcher_name": dispatcher_name if attribution_type == "dispatcher" else None,
                "attribution_type": attribution_type,
                "percent_snapshot": float(worker.get("percent_snapshot") or 0.0),
                "current_period_due_kopeks": max(_safe_int(worker.get("current_period_due_kopeks"), 0) or 0, 0),
                "current_period_paid_kopeks": max(_safe_int(worker.get("current_period_paid_kopeks"), 0) or 0, 0),
                "previous_debt_kopeks": max(_safe_int(worker.get("previous_debt_kopeks"), 0) or 0, 0),
                "amount_due_kopeks": max(_safe_int(worker.get("amount_due_kopeks"), 0) or 0, 0),
                "amount_paid_kopeks": max(_safe_int(worker.get("amount_paid_kopeks"), 0) or 0, 0),
                "amount_remaining_kopeks": max(_safe_int(worker.get("amount_remaining_kopeks"), 0) or 0, 0),
                "shifts": worker.get("shifts") if isinstance(worker.get("shifts"), list) else [],
                "previous_debts": worker.get("previous_debts") if isinstance(worker.get("previous_debts"), list) else [],
                "debt_closures": worker.get("debt_closures") if isinstance(worker.get("debt_closures"), list) else [],
            }
            normalized_workers.append(normalized_worker)

            totals_current_period_due_kopeks += normalized_worker["current_period_due_kopeks"]
            totals_previous_debt_kopeks += normalized_worker["previous_debt_kopeks"]
            totals_amount_due_kopeks += normalized_worker["amount_due_kopeks"]
            totals_amount_paid_kopeks += normalized_worker["amount_paid_kopeks"]
            totals_amount_remaining_kopeks += normalized_worker["amount_remaining_kopeks"]
            totals_shifts_count += len(normalized_worker["shifts"])

        if totals_amount_due_kopeks != amount_due_kopeks:
            return bad_request("amount_due_kopeks must match sum(workers[].amount_due_kopeks)")
        if totals_amount_paid_kopeks != amount_paid_kopeks:
            return bad_request("amount_paid_kopeks must match sum(workers[].amount_paid_kopeks)")

        event_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "firm_id": firm_id,
            "dispatcher_id": dispatcher_id,
            "dispatcher_name": dispatcher_name,
            "attribution_type": attribution_type,
            "amount_due_kopeks": totals_amount_due_kopeks,
            "amount_paid_kopeks": totals_amount_paid_kopeks,
            "amount_remaining_kopeks": totals_amount_remaining_kopeks,
            "event_at": event_at,
            "period_started_at": _to_iso_utc((last_scope_event or {}).get("created_at")) if last_scope_event else None,
            "period_ended_at": period_ended_at,
            "source_last_settlement_event_id": actual_last_event_id,
            "source_last_settlement_created_at": actual_last_created_at,
            "totals": {
                "current_period_due_kopeks": totals_current_period_due_kopeks,
                "previous_debt_kopeks": totals_previous_debt_kopeks,
                "amount_due_kopeks": totals_amount_due_kopeks,
                "amount_paid_kopeks": totals_amount_paid_kopeks,
                "amount_remaining_kopeks": totals_amount_remaining_kopeks,
                "workers_count": len(normalized_workers),
                "shifts_count": totals_shifts_count,
            },
            "workers": normalized_workers,
        }

        event_id = create_event_entity(
            caller_user_id,
            EVENT_DISPATCHER_SETTLEMENT,
            payload,
            logger,
            firm_id=firm_id,
            schema_version=2,
        )
    except Exception as e:
        logger.error("payroll_manager.dispatcher_settlement.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.dispatcher_settlement.event_failed", error=str(e))
        return server_error("Event generation failed")

    return created(
        {
            "message": "Dispatcher settlement created",
            "event_id": event_id,
            "firm_id": firm_id,
            "dispatcher_id": dispatcher_id,
            "attribution_type": attribution_type,
        }
    )
