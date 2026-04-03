# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

import ydb

from event_state import fetch_firm_event_states
from handlers_employee_finance import _coerce_datetime_utc
from internal_calls import call_vector_search_manager_search_objects
from utils import bad_request, ok_response, server_error
from utils.util_metadata import parse_json_value


DEFAULT_OBJECTS_PAGE_SIZE = 20
MAX_OBJECTS_PAGE_SIZE = 100
ASSIGN_EVENTS_LOOKBACK_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
SHIFT_FINANCE_TERMINAL_STATUSES = {"completed", "force_completed"}
DEAL_FINANCE_TERMINAL_STATUSES = {"archived", "completed", "force_completed"}


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        raw = value.strip().replace(" ", "").replace(",", ".")
        if not raw:
            return default
        try:
            return float(raw)
        except Exception:
            return default
    return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            return int(raw)
        except Exception:
            return default
    return default


def _rubles_to_kopeks(value: Any) -> int:
    amount_rub = _safe_float(value, 0.0)
    if amount_rub <= 0:
        return 0
    return int(
        (Decimal(str(amount_rub)) * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


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

def _extract_extra_charges_total_kopeks(raw_value: Any) -> int:
    parsed = parse_json_value(raw_value)
    if isinstance(parsed, dict) and isinstance(parsed.get("__value"), list):
        parsed = parsed.get("__value")
    if not isinstance(parsed, list):
        return 0

    total = 0
    for item in parsed:
        if not isinstance(item, dict):
            continue
        amount = item.get("amount")
        total += _rubles_to_kopeks(amount)
    return total


def _state_log_preview(state: Any) -> Dict[str, Any]:
    if not isinstance(state, dict):
        return {"state_type": type(state).__name__}
    preview: Dict[str, Any] = {
        "keys": sorted([_norm_text(key) for key in state.keys() if _norm_text(key)]),
    }
    for key in (
        "firm_id",
        "object_id",
        "shift_id",
        "deal_id",
        "worker_id",
        "assigned_by",
        "base_payment",
        "withholding",
        "dispatcher_percent_snapshot",
        "status",
        "event_at",
    ):
        if key in state:
            preview[key] = state.get(key)
    return preview


def _read_all_objects(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        SELECT object_id, object_name, status, contract_amount, extra_charges_json
        FROM firm_objects
        WHERE firm_id = $firm_id
        ORDER BY object_name ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            objects.append(
                {
                    "object_id": _norm_text(getattr(row, "object_id", None)),
                    "object_name": _norm_text(getattr(row, "object_name", None)),
                    "status": _norm_text(getattr(row, "status", None)),
                    "contract_amount_kopeks": _rubles_to_kopeks(
                        getattr(row, "contract_amount", None)
                    ),
                    "extra_charges_total_kopeks": _extract_extra_charges_total_kopeks(
                        getattr(row, "extra_charges_json", None)
                    ),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return [item for item in objects if item.get("object_id")]


def _read_all_shifts(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        SELECT
          s.shift_id AS shift_id,
          s.object_id AS object_id,
          s.base_payment AS base_payment,
          s.status AS status,
          s.created_at AS created_at
        FROM firm_shifts AS s
        INNER JOIN firm_objects AS o ON o.object_id = s.object_id
        WHERE o.firm_id = $firm_id
        ORDER BY created_at ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            shift_id = _norm_text(getattr(row, "shift_id", None))
            if not shift_id:
                continue
            rows_out.append(
                {
                    "shift_id": shift_id,
                    "object_id": _norm_text(getattr(row, "object_id", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "status": _norm_text(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return rows_out


def _read_all_deals(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        SELECT
          d.deal_id AS deal_id,
          d.object_id AS object_id,
          d.base_payment AS base_payment,
          d.status AS status,
          d.created_at AS created_at
        FROM firm_deals AS d
        INNER JOIN firm_objects AS o ON o.object_id = d.object_id
        WHERE o.firm_id = $firm_id
        ORDER BY created_at ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            deal_id = _norm_text(getattr(row, "deal_id", None))
            if not deal_id:
                continue
            rows_out.append(
                {
                    "deal_id": deal_id,
                    "object_id": _norm_text(getattr(row, "object_id", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "status": _norm_text(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return rows_out


def _read_assign_event_rows(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        SELECT event_id, event_type, created_at, sequence_number
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type IN ('shift_assign', 'deal_assign')
          AND created_at >= $start_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": ASSIGN_EVENTS_LOOKBACK_START},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = _norm_text(getattr(row, "event_id", None))
            if not event_id:
                continue
            rows_out.append(
                {
                    "event_id": event_id,
                    "event_type": _norm_text(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return rows_out


def _empty_object_metrics(object_row: Dict[str, Any]) -> Dict[str, Any]:
    contract_amount_kopeks = _safe_int(object_row.get("contract_amount_kopeks"), 0)
    extra_charges_total_kopeks = _safe_int(
        object_row.get("extra_charges_total_kopeks"),
        0,
    )
    return {
        "object_id": _norm_text(object_row.get("object_id")),
        "object_name": _norm_text(object_row.get("object_name")),
        "status": _norm_text(object_row.get("status")),
        "contract_amount_kopeks": contract_amount_kopeks,
        "extra_charges_total_kopeks": extra_charges_total_kopeks,
        "shifts_total_kopeks": 0,
        "deals_total_kopeks": 0,
        "withholds_total_kopeks": 0,
        "employee_payouts_kopeks": 0,
        "employee_costs_kopeks": 0,
        "object_costs_kopeks": 0,
        "gross_profit_kopeks": 0,
        "total_kopeks": contract_amount_kopeks + extra_charges_total_kopeks,
    }


def _collect_latest_object_activity_dates(
    *,
    shift_rows: List[Dict[str, Any]],
    deal_rows: List[Dict[str, Any]],
) -> Dict[str, datetime]:
    latest_by_object_id: Dict[str, datetime] = {}

    def _apply(object_id: Any, raw_created_at: Any) -> None:
        normalized_object_id = _norm_text(object_id)
        if not normalized_object_id:
            return
        created_at = _coerce_datetime_utc(raw_created_at)
        if created_at is None:
            return
        current = latest_by_object_id.get(normalized_object_id)
        if current is None or created_at > current:
            latest_by_object_id[normalized_object_id] = created_at

    for row in shift_rows:
        _apply(row.get("object_id"), row.get("created_at"))
    for row in deal_rows:
        _apply(row.get("object_id"), row.get("created_at"))
    return latest_by_object_id


def _extract_shift_assign_payload(state: Any) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise RuntimeError("shift_assign state must be an object")
    shift_id = _norm_text(state.get("shift_id"))
    if not shift_id:
        raise RuntimeError("shift_assign state missing shift_id")
    return {
        "shift_id": shift_id,
        "object_id": _norm_text(state.get("object_id")),
        "worker_id": _norm_text(state.get("worker_id")),
        "withholding_rub": _safe_float(state.get("withholding"), 0.0),
        "dispatcher_percent_snapshot": _safe_float(
            state.get("dispatcher_percent_snapshot"),
            0.0,
        ),
    }


def _extract_deal_assign_payload(state: Any) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise RuntimeError("deal_assign state must be an object")
    deal_id = _norm_text(state.get("deal_id"))
    if not deal_id:
        raise RuntimeError("deal_assign state missing deal_id")
    return {
        "deal_id": deal_id,
        "object_id": _norm_text(state.get("object_id")),
        "worker_id": _norm_text(state.get("worker_id")),
        "withholding_rub": _safe_float(state.get("withholding"), 0.0),
    }


def _build_latest_assign_maps(
    *,
    assign_event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
    target_shift_ids: List[str],
    target_deal_ids: List[str],
    logger,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    latest_shift_assign_by_shift_id: Dict[str, Dict[str, Any]] = {}
    latest_deal_assign_by_deal_id: Dict[str, Dict[str, Any]] = {}
    shift_id_set = {_norm_text(value) for value in target_shift_ids if _norm_text(value)}
    deal_id_set = {_norm_text(value) for value in target_deal_ids if _norm_text(value)}

    for row in assign_event_rows:
        event_id = _norm_text(row.get("event_id"))
        event_type = _norm_text(row.get("event_type")).lower()
        sequence_number = _safe_int(row.get("sequence_number"))
        if not event_id or sequence_number is None:
            continue
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            logger.warn(
                "analytics_getter.finance_assign.state_missing",
                event_id=event_id,
                event_type=event_type,
                created_at=row.get("created_at"),
            )
            continue

        try:
            if event_type == "shift_assign":
                payload = _extract_shift_assign_payload(state)
                shift_id = payload["shift_id"]
                if shift_id not in shift_id_set:
                    continue
                current = latest_shift_assign_by_shift_id.get(shift_id)
                if current is None or sequence_number > _safe_int(current.get("sequence_number"), -1):
                    latest_shift_assign_by_shift_id[shift_id] = {
                        **payload,
                        "sequence_number": sequence_number,
                        "created_at": _coerce_datetime_utc(row.get("created_at")),
                    }
            elif event_type == "deal_assign":
                payload = _extract_deal_assign_payload(state)
                deal_id = payload["deal_id"]
                if deal_id not in deal_id_set:
                    continue
                current = latest_deal_assign_by_deal_id.get(deal_id)
                if current is None or sequence_number > _safe_int(current.get("sequence_number"), -1):
                    latest_deal_assign_by_deal_id[deal_id] = {
                        **payload,
                        "sequence_number": sequence_number,
                        "created_at": _coerce_datetime_utc(row.get("created_at")),
                    }
        except Exception as exc:
            logger.warn(
                "analytics_getter.finance_assign.invalid_state_skipped",
                event_id=event_id,
                event_type=event_type,
                created_at=row.get("created_at"),
                state_preview=_state_log_preview(state),
                error=str(exc),
            )
            continue

    return latest_shift_assign_by_shift_id, latest_deal_assign_by_deal_id


def _build_object_metrics_map(
    *,
    objects: List[Dict[str, Any]],
    shift_rows: List[Dict[str, Any]],
    deal_rows: List[Dict[str, Any]],
    latest_shift_assign_by_shift_id: Dict[str, Dict[str, Any]],
    latest_deal_assign_by_deal_id: Dict[str, Dict[str, Any]],
    latest_activity_dates_by_object_id: Dict[str, datetime],
    logger,
) -> Dict[str, Dict[str, Any]]:
    metrics_by_object_id = {
        _norm_text(item.get("object_id")): _empty_object_metrics(item) for item in objects
    }
    for object_id, metrics in metrics_by_object_id.items():
        latest_activity = latest_activity_dates_by_object_id.get(object_id)
        metrics["latest_activity_at"] = (
            latest_activity.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            if isinstance(latest_activity, datetime)
            else None
        )

    for row in shift_rows:
        status = _norm_text(row.get("status")).lower()
        if status not in SHIFT_FINANCE_TERMINAL_STATUSES:
            continue
        shift_id = _norm_text(row.get("shift_id"))
        object_id = _norm_text(row.get("object_id"))
        if not shift_id or not object_id:
            continue
        metrics = metrics_by_object_id.get(object_id)
        if not isinstance(metrics, dict):
            continue
        assign_payload = latest_shift_assign_by_shift_id.get(shift_id)
        if not isinstance(assign_payload, dict):
            logger.warn(
                "analytics_getter.finance_shift.assign_missing_skipped",
                shift_id=shift_id,
                object_id=object_id,
                row_created_at=row.get("created_at"),
            )
            continue
        assign_object_id = _norm_text(assign_payload.get("object_id"))
        if assign_object_id and assign_object_id != object_id:
            logger.warn(
                "analytics_getter.finance_shift.assign_object_mismatch_skipped",
                shift_id=shift_id,
                row_object_id=object_id,
                assign_object_id=assign_object_id,
                row_created_at=row.get("created_at"),
            )
            continue

        shift_amount_kopeks = _rubles_to_kopeks(row.get("base_payment"))
        shift_withholding_kopeks = _rubles_to_kopeks(assign_payload.get("withholding_rub"))
        dispatcher_withhold_kopeks = _calculate_dispatcher_withhold_kopeks(
            shift_amount_kopeks,
            assign_payload.get("dispatcher_percent_snapshot"),
        )
        logger.info(
            "analytics_getter.finance_shift.contribution_applied",
            shift_id=shift_id,
            object_id=object_id,
            status=status,
            shift_amount_kopeks=shift_amount_kopeks,
            shift_withholding_kopeks=shift_withholding_kopeks,
            dispatcher_percent_snapshot=assign_payload.get("dispatcher_percent_snapshot"),
            dispatcher_withhold_kopeks=dispatcher_withhold_kopeks,
        )

        metrics["shifts_total_kopeks"] += shift_amount_kopeks
        metrics["withholds_total_kopeks"] += shift_withholding_kopeks
        metrics["employee_payouts_kopeks"] += max(
            shift_amount_kopeks - dispatcher_withhold_kopeks,
            0,
        )
        metrics["employee_costs_kopeks"] += shift_withholding_kopeks

    for row in deal_rows:
        status = _norm_text(row.get("status")).lower()
        if status not in DEAL_FINANCE_TERMINAL_STATUSES:
            continue
        deal_id = _norm_text(row.get("deal_id"))
        object_id = _norm_text(row.get("object_id"))
        if not deal_id or not object_id:
            continue
        metrics = metrics_by_object_id.get(object_id)
        if not isinstance(metrics, dict):
            continue
        assign_payload = latest_deal_assign_by_deal_id.get(deal_id)
        if not isinstance(assign_payload, dict):
            logger.warn(
                "analytics_getter.finance_deal.assign_missing_skipped",
                deal_id=deal_id,
                object_id=object_id,
                row_created_at=row.get("created_at"),
            )
            continue
        assign_object_id = _norm_text(assign_payload.get("object_id"))
        if assign_object_id and assign_object_id != object_id:
            logger.warn(
                "analytics_getter.finance_deal.assign_object_mismatch_skipped",
                deal_id=deal_id,
                row_object_id=object_id,
                assign_object_id=assign_object_id,
                row_created_at=row.get("created_at"),
            )
            continue

        deal_amount_kopeks = _rubles_to_kopeks(row.get("base_payment"))
        deal_withholding_kopeks = _rubles_to_kopeks(assign_payload.get("withholding_rub"))
        logger.info(
            "analytics_getter.finance_deal.contribution_applied",
            deal_id=deal_id,
            object_id=object_id,
            status=status,
            deal_amount_kopeks=deal_amount_kopeks,
            deal_withholding_kopeks=deal_withholding_kopeks,
        )

        metrics["deals_total_kopeks"] += deal_amount_kopeks
        metrics["withholds_total_kopeks"] += deal_withholding_kopeks
        metrics["employee_payouts_kopeks"] += deal_amount_kopeks
        metrics["employee_costs_kopeks"] += deal_withholding_kopeks

    for metrics in metrics_by_object_id.values():
        metrics["total_kopeks"] = (
            _safe_int(metrics.get("contract_amount_kopeks"), 0)
            + _safe_int(metrics.get("extra_charges_total_kopeks"), 0)
            + _safe_int(metrics.get("shifts_total_kopeks"), 0)
            + _safe_int(metrics.get("deals_total_kopeks"), 0)
            + _safe_int(metrics.get("withholds_total_kopeks"), 0)
        )

    return metrics_by_object_id


def _build_overall_summary(metrics_by_object_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    turnover_kopeks = 0
    employee_payouts_kopeks = 0
    employee_costs_kopeks = 0
    object_costs_kopeks = 0

    for metrics in metrics_by_object_id.values():
        turnover_kopeks += _safe_int(metrics.get("total_kopeks"), 0)
        employee_payouts_kopeks += _safe_int(metrics.get("employee_payouts_kopeks"), 0)
        employee_costs_kopeks += _safe_int(metrics.get("employee_costs_kopeks"), 0)
        object_costs_kopeks += _safe_int(metrics.get("object_costs_kopeks"), 0)

    return {
        "turnover_kopeks": turnover_kopeks,
        "gross_profit_kopeks": 0,
        "employee_payouts_kopeks": employee_payouts_kopeks,
        "employee_costs_kopeks": employee_costs_kopeks,
        "object_costs_kopeks": object_costs_kopeks,
        "objects_count": len(metrics_by_object_id),
    }


def _sorted_object_ids_by_activity(
    object_ids: List[str],
    metrics_by_object_id: Dict[str, Dict[str, Any]],
) -> List[str]:
    ordered_ids = [
        _norm_text(object_id)
        for object_id in object_ids
        if _norm_text(object_id)
    ]
    ordered_ids = sorted(
        ordered_ids,
        key=lambda object_id: (
            _norm_text((metrics_by_object_id.get(object_id) or {}).get("object_name")),
            object_id,
        ),
    )
    ordered_ids.sort(
        key=lambda object_id: (
            _coerce_datetime_utc(
                (metrics_by_object_id.get(object_id) or {}).get("latest_activity_at")
            )
            or datetime(1970, 1, 1, tzinfo=timezone.utc)
        ),
        reverse=True,
    )
    return ordered_ids


def _build_summary_context(
    *,
    firm_id: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
) -> Dict[str, Any]:
    objects = _read_all_objects(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
    )
    shift_rows = _read_all_shifts(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
    )
    deal_rows = _read_all_deals(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
    )
    latest_activity_dates_by_object_id = _collect_latest_object_activity_dates(
        shift_rows=shift_rows,
        deal_rows=deal_rows,
    )
    shift_ids = [
        _norm_text(item.get("shift_id"))
        for item in shift_rows
        if _norm_text(item.get("shift_id"))
    ]
    deal_ids = [
        _norm_text(item.get("deal_id"))
        for item in deal_rows
        if _norm_text(item.get("deal_id"))
    ]
    assign_event_rows = _read_assign_event_rows(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
    )
    event_states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=[item["event_id"] for item in assign_event_rows],
        logger=logger,
    )
    latest_shift_assign_by_shift_id, latest_deal_assign_by_deal_id = _build_latest_assign_maps(
        assign_event_rows=assign_event_rows,
        states_by_event_id=event_states,
        target_shift_ids=shift_ids,
        target_deal_ids=deal_ids,
        logger=logger,
    )
    metrics_by_object_id = _build_object_metrics_map(
        objects=objects,
        shift_rows=shift_rows,
        deal_rows=deal_rows,
        latest_shift_assign_by_shift_id=latest_shift_assign_by_shift_id,
        latest_deal_assign_by_deal_id=latest_deal_assign_by_deal_id,
        latest_activity_dates_by_object_id=latest_activity_dates_by_object_id,
        logger=logger,
    )
    ordered_object_ids = _sorted_object_ids_by_activity(
        [
            _norm_text(item.get("object_id"))
            for item in objects
            if _norm_text(item.get("object_id"))
        ],
        metrics_by_object_id,
    )
    overall = _build_overall_summary(metrics_by_object_id)
    logger.info(
        "analytics_getter.finance_objects_summary.context_built",
        firm_id=firm_id,
        objects_count=len(objects),
        shift_rows_count=len(shift_rows),
        deal_rows_count=len(deal_rows),
        assign_event_rows_count=len(assign_event_rows),
        matched_shift_assigns_count=len(latest_shift_assign_by_shift_id),
        matched_deal_assigns_count=len(latest_deal_assign_by_deal_id),
        overall=overall,
    )
    return {
        "objects": objects,
        "ordered_object_ids": ordered_object_ids,
        "metrics_by_object_id": metrics_by_object_id,
        "overall": overall,
    }


def handle_finance_turnover(
    body,
    firm_id,
    events_pool,
    events_database,
    firms_pool,
    firms_database,
    objects_pool,
    objects_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.finance_turnover.start", firm_id=firm_id)

    try:
        summary_context = _build_summary_context(
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        overall = summary_context["overall"]

        logger.info(
            "analytics_getter.finance_turnover.success",
            firm_id=firm_id,
            turnover_kopeks=overall.get("turnover_kopeks"),
        )

        return ok_response(
            {
                "firm_id": firm_id,
                "turnover_kopeks": overall["turnover_kopeks"],
                "gross_profit_kopeks": overall["gross_profit_kopeks"],
                "employee_payouts_kopeks": overall["employee_payouts_kopeks"],
                "employee_costs_kopeks": overall["employee_costs_kopeks"],
                "object_costs_kopeks": overall["object_costs_kopeks"],
                "objects_count": overall["objects_count"],
            }
        )

    except Exception as e:
        logger.error("analytics_getter.finance_turnover.error", error=str(e))
        hlog.exception("analytics_getter.finance_turnover.error", error=str(e))
        return server_error("Internal Server Error")


def handle_finance_gross_profit(
    body,
    firm_id,
    events_pool,
    events_database,
    firms_pool,
    firms_database,
    objects_pool,
    objects_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.finance_gross_profit.start", firm_id=firm_id)

    try:
        summary_context = _build_summary_context(
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        overall = summary_context["overall"]

        logger.info(
            "analytics_getter.finance_gross_profit.success",
            firm_id=firm_id,
            gross_profit_kopeks=overall.get("gross_profit_kopeks"),
        )

        return ok_response(
            {
                "firm_id": firm_id,
                "gross_profit_kopeks": overall["gross_profit_kopeks"],
            }
        )

    except Exception as e:
        logger.error("analytics_getter.finance_gross_profit.error", error=str(e))
        hlog.exception("analytics_getter.finance_gross_profit.error", error=str(e))
        return server_error("Internal Server Error")


def handle_finance_objects_summary(
    body,
    firm_id,
    caller_user_id,
    caller_role_type,
    objects_pool,
    objects_database,
    events_pool,
    events_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.finance_objects_summary.start", firm_id=firm_id)

    search_query = _norm_text(body.get("search_query"))
    page = body.get("page", 0)
    page_size = body.get("page_size", DEFAULT_OBJECTS_PAGE_SIZE)

    try:
        page = int(page)
    except Exception:
        return bad_request("page must be a non-negative integer")
    try:
        page_size = int(page_size)
    except Exception:
        return bad_request("page_size must be an integer between 1 and 100")

    if page < 0:
        return bad_request("page must be a non-negative integer")
    if page_size < 1 or page_size > MAX_OBJECTS_PAGE_SIZE:
        return bad_request("page_size must be between 1 and 100")

    try:
        summary_context = _build_summary_context(
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        objects = summary_context["objects"]
        ordered_object_ids = summary_context["ordered_object_ids"]
        metrics_by_object_id = summary_context["metrics_by_object_id"]
        overall = summary_context["overall"]

        object_ids_on_page: List[str] = []
        has_next = False

        if search_query:
            vector_response = call_vector_search_manager_search_objects(
                initiator_user_id=caller_user_id,
                initiator_role_type=caller_role_type,
                firm_id=firm_id,
                query=search_query,
                page=page,
                page_size=page_size,
                logger=logger,
                hlog=hlog,
            )
            vector_items = (
                vector_response.get("items")
                if isinstance(vector_response, dict)
                else None
            )
            if isinstance(vector_items, list):
                for item in vector_items:
                    if not isinstance(item, dict):
                        continue
                    entity_id = _norm_text(item.get("entity_id"))
                    if entity_id:
                        object_ids_on_page.append(entity_id)
            object_ids_on_page = _sorted_object_ids_by_activity(
                object_ids_on_page,
                metrics_by_object_id,
            )
            has_next = bool(
                vector_response.get("has_more")
                if isinstance(vector_response, dict)
                else False
            )
        else:
            start = page * page_size
            end = start + page_size
            object_ids_on_page = ordered_object_ids[start:end]
            has_next = end < len(ordered_object_ids)

        items: List[Dict[str, Any]] = []
        for object_id in object_ids_on_page:
            metrics = metrics_by_object_id.get(object_id)
            if not isinstance(metrics, dict):
                continue
            items.append(metrics)

        logger.info(
            "analytics_getter.finance_objects_summary.success",
            firm_id=firm_id,
            items_count=len(items),
            has_next=has_next,
            search_query=search_query or None,
            overall=overall,
        )

        return ok_response(
            {
                "firm_id": firm_id,
                "overall": overall,
                "page": page,
                "page_size": page_size,
                "has_next": has_next,
                "has_prev": page > 0,
                "items": items,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.finance_objects_summary.error", error=str(e))
        hlog.exception("analytics_getter.finance_objects_summary.error", error=str(e))
        return server_error("Internal Server Error")
