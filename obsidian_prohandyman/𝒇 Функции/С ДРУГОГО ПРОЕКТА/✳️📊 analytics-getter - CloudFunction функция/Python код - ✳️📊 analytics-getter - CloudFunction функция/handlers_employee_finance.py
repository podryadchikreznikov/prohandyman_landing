# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Set, Tuple

import ydb

from utils import bad_request, ok_response, server_error
from utils.util_metadata import parse_json_value

from event_state import extract_amount_kopeks, extract_user_id, fetch_firm_event_states

FINANCE_EVENT_TYPES: Tuple[str, ...] = (
    "accrual",
    "cash",
    "withheld_shift",
    "withhold_accrual",
    "obj_costs",
    "emp_costs",
    "reward",
    "fine",
    "shift_end",
    "deal_complete",
    "deferred",
    # Legacy alias kept for backward compatibility with old event streams.
    "accrual_deferred",
)

FINANCE_EVENT_TYPES_SQL = ", ".join(
    [
        f"'{x}'"
        for x in sorted(
            {
                normalized
                for raw in FINANCE_EVENT_TYPES
                for normalized in (
                    str(raw).strip(),
                    str(raw).strip().lower(),
                    str(raw).strip().upper(),
                )
                if normalized
            }
        )
    ]
)

NEGATIVE_PENDING_TYPES = {
    "FINE",
    "WITHHELD_SHIFT",
    "WITHHOLD_ACCRUAL",
    "OBJ_COSTS",
    "EMP_COSTS",
}
PAID_TYPES = {"CASH"}
REWARDS_FINES_SOURCE_TYPES = {"REWARD", *NEGATIVE_PENDING_TYPES}

CASH_PLAN_EVENT_TYPES: Tuple[str, ...] = (
    "accrual",
    "cash",
    "reward",
    "fine",
    "withheld_shift",
    "withhold_accrual",
    "obj_costs",
    "emp_costs",
)

CASH_PLAN_EVENT_TYPES_SQL = ", ".join(
    [
        f"'{x}'"
        for x in sorted(
            {
                normalized
                for raw in CASH_PLAN_EVENT_TYPES
                for normalized in (
                    str(raw).strip(),
                    str(raw).strip().lower(),
                    str(raw).strip().upper(),
                )
                if normalized
            }
        )
    ]
)

CURRENT_SOURCE_EVENT_TYPES = {
    "REWARD",
    "FINE",
    "SHIFT_END",
    "DEAL_COMPLETE",
}
DEFERRED_MARKER_EVENT_TYPES = {
    "DEFERRED",
    "ACCRUAL_DEFERRED",
}

MAX_PAGE_SIZE = 100
ASSIGN_EVENTS_LOOKBACK_START = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _norm_text(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except Exception:
            value = str(value)
    if value is None:
        return ""
    return str(value).strip()


def _coerce_datetime_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        raw = float(value)
        abs_raw = abs(raw)
        try:
            if abs_raw >= 1e14:
                return datetime.fromtimestamp(raw / 1_000_000, tz=timezone.utc)
            if abs_raw >= 1e11:
                return datetime.fromtimestamp(raw / 1_000, tz=timezone.utc)
            if abs_raw >= 1e9:
                return datetime.fromtimestamp(raw, tz=timezone.utc)
        except Exception:
            return None
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return _coerce_datetime_utc(float(text))
        except Exception:
            pass
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


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


def _to_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return dt.date().isoformat()
        except Exception:
            return text
    return text


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except Exception:
            return None
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


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


def _month_range(*, year: int, month: int) -> Tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _year_range(*, year: int) -> Tuple[datetime, datetime]:
    return datetime(year, 1, 1, tzinfo=timezone.utc), datetime(year + 1, 1, 1, tzinfo=timezone.utc)


def _parse_month_year(body: dict) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    month = _safe_int(body.get("month"))
    year = _safe_int(body.get("year"))
    if month is None or year is None:
        return None, None, "month and year are required"
    if month < 1 or month > 12:
        return None, None, "month must be an integer between 1 and 12"
    if year < 2020 or year > 2100:
        return None, None, "year must be an integer between 2020 and 2100"
    return month, year, None


def _parse_page(body: dict) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    page = _safe_int(body.get("page"), 0)
    page_size = _safe_int(body.get("page_size"), 50)
    if page is None or page < 0:
        return None, None, "page must be a non-negative integer"
    if page_size is None or page_size < 1 or page_size > MAX_PAGE_SIZE:
        return None, None, f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}"
    return page, page_size, None


def _extract_state_user_id(state: Any) -> str:
    user_id = _norm_text(extract_user_id(state))
    if user_id:
        return user_id
    if not isinstance(state, dict):
        return ""
    for key in ("completed_by", "assigned_by", "canceled_by"):
        value = _norm_text(state.get(key))
        if value:
            return value
    metadata = state.get("metadata")
    if isinstance(metadata, dict):
        nested = _norm_text(extract_user_id(metadata))
        if nested:
            return nested
    return ""


def _extract_object_id(state: Any) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in ("object_id", "obj_id"):
        value = _norm_text(state.get(key))
        if value:
            return value
    obj_block = state.get("object")
    if isinstance(obj_block, dict):
        for key in ("object_id", "id"):
            value = _norm_text(obj_block.get(key))
            if value:
                return value
    return None


def _extract_amount_fallback_kopeks(state: Any) -> Optional[int]:
    if not isinstance(state, dict):
        return None
    amount = state.get("amount")
    if isinstance(amount, int):
        return amount
    if isinstance(amount, float) and amount.is_integer():
        return int(amount)
    if isinstance(amount, str):
        text = amount.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            try:
                return int(text)
            except Exception:
                return None
    return None


def _chunked(values: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        return [values]
    return [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]


def _read_shift_rows_by_ids(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    shift_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    normalized_ids = [_norm_text(value) for value in shift_ids if _norm_text(value)]
    if not normalized_ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for chunk in _chunked(normalized_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{objects_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $shift_ids AS List<Utf8>;
            SELECT
              s.shift_id AS shift_id,
              s.object_id AS object_id,
              s.base_payment AS base_payment,
              s.status AS status,
              s.created_at AS created_at
            FROM firm_shifts AS s
            INNER JOIN firm_objects AS o ON o.object_id = s.object_id
            WHERE o.firm_id = $firm_id
              AND s.shift_id IN $shift_ids;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id, "$shift_ids": chunk},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                shift_id = _norm_text(getattr(row, "shift_id", None))
                if not shift_id:
                    continue
                out[shift_id] = {
                    "shift_id": shift_id,
                    "object_id": _norm_text(getattr(row, "object_id", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "status": _norm_text(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                }

        objects_pool.retry_operation_sync(_tx)

    return out


def _read_deal_rows_by_ids(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    deal_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    normalized_ids = [_norm_text(value) for value in deal_ids if _norm_text(value)]
    if not normalized_ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for chunk in _chunked(normalized_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{objects_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $deal_ids AS List<Utf8>;
            SELECT
              d.deal_id AS deal_id,
              d.object_id AS object_id,
              d.base_payment AS base_payment,
              d.status AS status,
              d.created_at AS created_at
            FROM firm_deals AS d
            INNER JOIN firm_objects AS o ON o.object_id = d.object_id
            WHERE o.firm_id = $firm_id
              AND d.deal_id IN $deal_ids;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id, "$deal_ids": chunk},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                deal_id = _norm_text(getattr(row, "deal_id", None))
                if not deal_id:
                    continue
                out[deal_id] = {
                    "deal_id": deal_id,
                    "object_id": _norm_text(getattr(row, "object_id", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "status": _norm_text(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                }

        objects_pool.retry_operation_sync(_tx)

    return out


def _read_assign_event_rows_for_work_items(
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


def _extract_shift_assign_payload(state: Any) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise RuntimeError("shift_assign state must be an object")
    shift_id = _norm_text(state.get("shift_id"))
    if not shift_id:
        raise RuntimeError("shift_assign state missing shift_id")
    dispatcher_attribution_raw = (
        state.get("dispatcher_attribution")
        if isinstance(state.get("dispatcher_attribution"), dict)
        else None
    )
    dispatcher_attribution = None
    if isinstance(dispatcher_attribution_raw, dict):
        dispatcher_attribution = {
            "dispatcher_id": _norm_text(dispatcher_attribution_raw.get("dispatcher_id")) or None,
            "dispatcher_name": _norm_text(dispatcher_attribution_raw.get("dispatcher_name")) or None,
            "attribution_type": _norm_text(dispatcher_attribution_raw.get("attribution_type")).lower() or None,
            "percent_snapshot": _safe_float(
                dispatcher_attribution_raw.get("percent_snapshot"),
                0.0,
            ),
            "created_at": _norm_text(dispatcher_attribution_raw.get("created_at")) or None,
            "updated_at": _norm_text(dispatcher_attribution_raw.get("updated_at")) or None,
        }
    return {
        "shift_id": shift_id,
        "object_id": _norm_text(state.get("object_id")),
        "worker_id": _norm_text(state.get("worker_id")),
        "withholding_rub": _safe_float(state.get("withholding"), 0.0),
        "dispatcher_percent_snapshot": _safe_float(
            state.get("dispatcher_percent_snapshot"),
            0.0,
        ),
        "dispatcher_attribution": dispatcher_attribution,
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


def _build_latest_work_item_assign_maps(
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
            continue
        try:
            if event_type == "shift_assign":
                payload = _extract_shift_assign_payload(state)
                shift_id = payload["shift_id"]
                if shift_id not in shift_id_set:
                    continue
                current = latest_shift_assign_by_shift_id.get(shift_id)
                if current is None or sequence_number > (_safe_int(current.get("sequence_number"), -1) or -1):
                    latest_shift_assign_by_shift_id[shift_id] = {
                        **payload,
                        "sequence_number": sequence_number,
                        "created_at": row.get("created_at"),
                    }
            elif event_type == "deal_assign":
                payload = _extract_deal_assign_payload(state)
                deal_id = payload["deal_id"]
                if deal_id not in deal_id_set:
                    continue
                current = latest_deal_assign_by_deal_id.get(deal_id)
                if current is None or sequence_number > (_safe_int(current.get("sequence_number"), -1) or -1):
                    latest_deal_assign_by_deal_id[deal_id] = {
                        **payload,
                        "sequence_number": sequence_number,
                        "created_at": row.get("created_at"),
                    }
        except Exception as exc:
            logger.warn(
                "analytics_getter.employee_finance.work_item_assign_invalid",
                event_id=event_id,
                event_type=event_type,
                error=str(exc),
            )
            continue

    return latest_shift_assign_by_shift_id, latest_deal_assign_by_deal_id


def _build_work_item_amount_context(
    *,
    events: List[Dict[str, Any]],
    firm_id: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
) -> Dict[str, Any]:
    shift_ids = sorted(
        {
            _norm_text((item.get("state") or {}).get("shift_id"))
            for item in events
            if _norm_text(item.get("event_type_upper")) == "SHIFT_END"
            and isinstance(item.get("state"), dict)
            and _norm_text((item.get("state") or {}).get("shift_id"))
        }
    )
    deal_ids = sorted(
        {
            _norm_text((item.get("state") or {}).get("deal_id"))
            for item in events
            if _norm_text(item.get("event_type_upper")) == "DEAL_COMPLETE"
            and isinstance(item.get("state"), dict)
            and _norm_text((item.get("state") or {}).get("deal_id"))
        }
    )
    if not shift_ids and not deal_ids:
        return {
            "shift_rows_by_id": {},
            "deal_rows_by_id": {},
            "latest_shift_assign_by_shift_id": {},
            "latest_deal_assign_by_deal_id": {},
        }

    shift_rows_by_id = _read_shift_rows_by_ids(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        shift_ids=shift_ids,
    )
    deal_rows_by_id = _read_deal_rows_by_ids(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        deal_ids=deal_ids,
    )
    assign_event_rows = _read_assign_event_rows_for_work_items(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
    )
    assign_event_ids = [
        _norm_text(item.get("event_id"))
        for item in assign_event_rows
        if _norm_text(item.get("event_id"))
    ]
    assign_states_by_event_id = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=assign_event_ids,
        logger=logger,
    )
    latest_shift_assign_by_shift_id, latest_deal_assign_by_deal_id = _build_latest_work_item_assign_maps(
        assign_event_rows=assign_event_rows,
        states_by_event_id=assign_states_by_event_id,
        target_shift_ids=shift_ids,
        target_deal_ids=deal_ids,
        logger=logger,
    )
    logger.info(
        "analytics_getter.employee_finance.work_item_amount_context",
        firm_id=firm_id,
        shift_ids_count=len(shift_ids),
        deal_ids_count=len(deal_ids),
        shift_rows_count=len(shift_rows_by_id),
        deal_rows_count=len(deal_rows_by_id),
        assign_event_rows_count=len(assign_event_rows),
        matched_shift_assigns_count=len(latest_shift_assign_by_shift_id),
        matched_deal_assigns_count=len(latest_deal_assign_by_deal_id),
    )
    return {
        "shift_rows_by_id": shift_rows_by_id,
        "deal_rows_by_id": deal_rows_by_id,
        "latest_shift_assign_by_shift_id": latest_shift_assign_by_shift_id,
        "latest_deal_assign_by_deal_id": latest_deal_assign_by_deal_id,
    }


def _enrich_work_item_amounts(
    *,
    events: List[Dict[str, Any]],
    amount_context: Dict[str, Any],
    logger,
) -> List[Dict[str, Any]]:
    if not events:
        return []

    shift_rows_by_id = amount_context.get("shift_rows_by_id") or {}
    deal_rows_by_id = amount_context.get("deal_rows_by_id") or {}
    latest_shift_assign_by_shift_id = amount_context.get("latest_shift_assign_by_shift_id") or {}
    latest_deal_assign_by_deal_id = amount_context.get("latest_deal_assign_by_deal_id") or {}

    enriched: List[Dict[str, Any]] = []
    enriched_shifts = 0
    enriched_deals = 0

    for item in events:
        normalized_item = dict(item)
        event_type_upper = _norm_text(normalized_item.get("event_type_upper"))
        amount_kopeks = normalized_item.get("amount_kopeks")
        state = normalized_item.get("state") if isinstance(normalized_item.get("state"), dict) else {}

        if event_type_upper == "SHIFT_END":
            shift_id = _norm_text(state.get("shift_id"))
            assign_payload = latest_shift_assign_by_shift_id.get(shift_id)
            if isinstance(assign_payload, dict):
                normalized_item["work_item_assign"] = assign_payload
            if not isinstance(amount_kopeks, int):
                shift_row = shift_rows_by_id.get(shift_id)
                if isinstance(shift_row, dict):
                    normalized_item["amount_kopeks"] = _rubles_to_kopeks(shift_row.get("base_payment"))
                    normalized_item["object_id"] = _norm_text(normalized_item.get("object_id")) or _norm_text(shift_row.get("object_id")) or None
                    enriched_shifts += 1
                else:
                    logger.warn(
                        "analytics_getter.employee_finance.shift_amount_source_missing",
                        event_id=_norm_text(normalized_item.get("event_id")),
                        shift_id=shift_id,
                    )
        elif event_type_upper == "DEAL_COMPLETE":
            deal_id = _norm_text(state.get("deal_id"))
            assign_payload = latest_deal_assign_by_deal_id.get(deal_id)
            if isinstance(assign_payload, dict):
                normalized_item["work_item_assign"] = assign_payload
            if not isinstance(amount_kopeks, int):
                deal_row = deal_rows_by_id.get(deal_id)
                if isinstance(deal_row, dict):
                    normalized_item["amount_kopeks"] = _rubles_to_kopeks(deal_row.get("base_payment"))
                    normalized_item["object_id"] = _norm_text(normalized_item.get("object_id")) or _norm_text(deal_row.get("object_id")) or None
                    enriched_deals += 1
                else:
                    logger.warn(
                        "analytics_getter.employee_finance.deal_amount_source_missing",
                        event_id=_norm_text(normalized_item.get("event_id")),
                        deal_id=deal_id,
                    )

        enriched.append(normalized_item)

    logger.info(
        "analytics_getter.employee_finance.work_item_amounts_enriched",
        events_count=len(events),
        enriched_shifts=enriched_shifts,
        enriched_deals=enriched_deals,
    )
    return enriched


def _read_finance_event_rows(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    start: datetime,
    end: datetime,
    event_types_sql: str = FINANCE_EVENT_TYPES_SQL,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at, updated_at
        FROM finance_events
        WHERE firm_id = $firm_id
          AND event_type IN ({event_types_sql})
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": start, "$end_at": end},
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


def _read_dispatcher_percent(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    user_id: str,
) -> float:
    percent = 0.0

    def _tx(session: ydb.Session):
        nonlocal percent
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $user_id AS Utf8;
        SELECT percent_snapshot
        FROM dispatcher_attributions
        WHERE firm_id = $firm_id AND worker_user_id = $user_id
        ORDER BY
            CASE
                WHEN attribution_type = 'dispatcher' THEN 0
                WHEN attribution_type = 'nominal' THEN 1
                ELSE 2
            END ASC,
            updated_at DESC,
            created_at DESC
        LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$user_id": user_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        if not rows:
            return
        value = getattr(rows[0], "percent_snapshot", 0.0)
        try:
            percent = float(value or 0.0)
        except Exception:
            percent = 0.0

    firms_pool.retry_operation_sync(_tx)
    return percent


def _read_objects_by_ids(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    object_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not object_ids:
        return {}

    unique_ids: List[str] = []
    seen: Set[str] = set()
    for object_id in object_ids:
        norm = _norm_text(object_id)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_ids.append(norm)

    if not unique_ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}

    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{objects_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $object_ids AS List<Utf8>;
            SELECT object_id, object_name, status, address_json
            FROM firm_objects
            WHERE firm_id = $firm_id
              AND object_id IN $object_ids;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id, "$object_ids": chunk},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                oid = _norm_text(getattr(row, "object_id", None))
                if not oid:
                    continue
                address = parse_json_value(getattr(row, "address_json", None))
                out[oid] = {
                    "object_id": oid,
                    "object_name": _norm_text(getattr(row, "object_name", None)) or None,
                    "status": _norm_text(getattr(row, "status", None)) or None,
                    "address_json": address,
                }

        objects_pool.retry_operation_sync(_tx)

    return out


def _read_fine_disputes_by_event_ids(
    *,
    appeals_pool: Optional[ydb.SessionPool],
    appeals_database: Optional[str],
    firm_id: str,
    event_ids: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    if not event_ids:
        return {}
    if appeals_pool is None:
        return {}
    if not _norm_text(appeals_database):
        return {}

    out: Dict[str, List[Dict[str, Any]]] = {}
    unique_ids: List[str] = []
    seen: Set[str] = set()
    for event_id in event_ids:
        norm = _norm_text(event_id)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_ids.append(norm)

    if not unique_ids:
        return {}

    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{appeals_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $source_type AS Utf8;
            DECLARE $source_event_ids AS List<Utf8>;
            SELECT appeal_id, status, user_id, created_at, updated_at, object_id, deal_id
            FROM Appeals
            WHERE firm_id = $firm_id
              AND shift_id = $source_type
              AND deal_id IN $source_event_ids
            ORDER BY created_at DESC;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {
                    "$firm_id": firm_id,
                    "$source_type": "fine",
                    "$source_event_ids": chunk,
                },
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                source_event_id = _norm_text(getattr(row, "deal_id", None))
                if not source_event_id:
                    continue
                out.setdefault(source_event_id, []).append(
                    {
                        "appeal_id": _norm_text(getattr(row, "appeal_id", None)),
                        "status": _norm_text(getattr(row, "status", None)),
                        "user_id": _norm_text(getattr(row, "user_id", None)),
                        "object_id": _norm_text(getattr(row, "object_id", None)) or None,
                        "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                        "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                    }
                )

        appeals_pool.retry_operation_sync(_tx)

    return out


def _to_fine_dispute_summary(disputes: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = disputes if isinstance(disputes, list) else []
    latest = items[0] if items else None
    return {
        "has_dispute": len(items) > 0,
        "disputes_count": len(items),
        "latest_dispute": latest,
    }


def _read_employee_salary_snapshot(
    *,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    firm_id: str,
    user_id: str,
    as_of: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{notices_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $user_id AS Utf8;
        DECLARE $as_of AS Timestamp;
        SELECT salary_id, amount, payout_date, last_payout_at, status, effective_from, deleted_at, created_at, updated_at
        FROM employee_salary
        WHERE firm_id = $firm_id
          AND user_id = $user_id
          AND (effective_from IS NULL OR effective_from <= $as_of)
          AND (deleted_at IS NULL OR deleted_at > $as_of)
        ORDER BY payout_date ASC, effective_from ASC, deleted_at ASC, created_at ASC, salary_id ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {
                "$firm_id": firm_id,
                "$user_id": user_id,
                "$as_of": as_of or datetime.now(timezone.utc),
            },
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            salary_id = _norm_text(getattr(row, "salary_id", None))
            if not salary_id:
                continue
            out.append(
                {
                    "salary_id": salary_id,
                    "amount_kopeks": _safe_int(getattr(row, "amount", None), 0) or 0,
                    "payout_date": _to_iso_date(getattr(row, "payout_date", None)),
                    "last_payout_at": _to_iso_utc(getattr(row, "last_payout_at", None)),
                    "status": _norm_text(getattr(row, "status", None)) or "active",
                    "effective_from": _to_iso_utc(getattr(row, "effective_from", None)),
                    "deleted_at": _to_iso_utc(getattr(row, "deleted_at", None)),
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }
            )

    notices_pool.retry_operation_sync(_tx)
    return out


def _filter_salary_snapshot_for_current_period(
    *,
    salary_snapshot: List[Dict[str, Any]],
    lower_bound: Optional[datetime],
    as_of: datetime,
) -> List[Dict[str, Any]]:
    as_of_date = as_of.date()
    if lower_bound is None:
        return [
            dict(item)
            for item in salary_snapshot
            if isinstance(item, dict)
            and (
                (_coerce_date(item.get("payout_date")) or as_of_date) <= as_of_date
            )
        ]

    lower_bound_date = lower_bound.date()
    filtered: List[Dict[str, Any]] = []
    for item in salary_snapshot:
        if not isinstance(item, dict):
            continue

        payout_date = _coerce_date(item.get("payout_date"))
        if payout_date is not None and payout_date > as_of_date:
            continue

        is_due_in_period = payout_date is not None and lower_bound_date < payout_date <= as_of_date
        is_touched_in_period = False
        for key in ("updated_at", "created_at", "effective_from"):
            ts = _coerce_datetime_utc(item.get(key))
            if ts is None:
                continue
            if lower_bound < ts <= as_of:
                is_touched_in_period = True
                break

        if is_due_in_period or is_touched_in_period:
            filtered.append(dict(item))

    return filtered


def _read_dispatcher_attribution(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    user_id: str,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $user_id AS Utf8;
        SELECT dispatcher_id, percent_snapshot, created_at, updated_at
        FROM dispatcher_attributions
        WHERE firm_id = $firm_id
          AND worker_user_id = $user_id
        ORDER BY
            CASE
                WHEN attribution_type = 'dispatcher' THEN 0
                WHEN attribution_type = 'nominal' THEN 1
                ELSE 2
            END ASC,
            updated_at DESC,
            created_at DESC
        LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$user_id": user_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        if not rows:
            return
        row = rows[0]
        percent_snapshot = getattr(row, "percent_snapshot", None)
        try:
            percent_snapshot = float(percent_snapshot or 0.0)
        except Exception:
            percent_snapshot = 0.0
        out.update(
            {
                "dispatcher_id": _norm_text(getattr(row, "dispatcher_id", None)) or None,
                "percent_snapshot": percent_snapshot,
                "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
            }
        )

    firms_pool.retry_operation_sync(_tx)
    return out


def _event_created_at(item: Dict[str, Any]) -> datetime:
    return _coerce_datetime_utc(item.get("created_at")) or datetime(
        1970, 1, 1, tzinfo=timezone.utc
    )


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
        percent_snapshot = _safe_float(dispatcher_attribution.get("percent_snapshot"), 0.0)
        gross_amount_kopeks = abs(amount_kopeks)
        dispatcher_withhold_kopeks = _calculate_dispatcher_withhold_kopeks(
            gross_amount_kopeks,
            percent_snapshot,
        )
        total += max(gross_amount_kopeks - dispatcher_withhold_kopeks, 0)
    return total


def _extract_deferred_state(
    *,
    user_events: List[Dict[str, Any]],
    last_accrual: Optional[Dict[str, Any]],
    as_of: datetime,
) -> Dict[str, Any]:
    lower_bound = _event_created_at(last_accrual) if isinstance(last_accrual, dict) else None
    latest_deferred: Optional[Dict[str, Any]] = None

    for item in user_events:
        created_at = _event_created_at(item)
        if lower_bound is not None and created_at <= lower_bound:
            continue
        event_type_upper = _norm_text(item.get("event_type_upper"))
        if event_type_upper not in DEFERRED_MARKER_EVENT_TYPES:
            continue
        if latest_deferred is None or _event_sort_key(item) > _event_sort_key(latest_deferred):
            latest_deferred = item

    if latest_deferred is None:
        return {
            "is_deferred": False,
            "deferred_until": None,
            "deferred_event_id": None,
            "accrual_event_id": None,
            "event_at": None,
        }

    state = latest_deferred.get("state") if isinstance(latest_deferred.get("state"), dict) else {}
    deferred_until_raw = _norm_text(state.get("deferred_until")) or None
    deferred_until_dt: Optional[datetime] = None
    if deferred_until_raw:
        try:
            deferred_until_dt = datetime.fromisoformat(deferred_until_raw.replace("Z", "+00:00"))
            if deferred_until_dt.tzinfo is None:
                deferred_until_dt = deferred_until_dt.replace(tzinfo=timezone.utc)
            else:
                deferred_until_dt = deferred_until_dt.astimezone(timezone.utc)
        except Exception:
            deferred_until_dt = None

    is_active = deferred_until_dt is not None and deferred_until_dt >= as_of
    return {
        "is_deferred": is_active,
        "deferred_until": deferred_until_raw,
        "deferred_event_id": _norm_text(latest_deferred.get("event_id")) or None,
        "accrual_event_id": None,
        "event_at": _to_iso_utc(latest_deferred.get("created_at")),
    }


def _resolve_period_as_of(period_end: datetime) -> datetime:
    now_utc = datetime.now(timezone.utc)
    as_of = min(now_utc, period_end - timedelta(seconds=1))
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = as_of.astimezone(timezone.utc)
    return as_of


def _build_current_finance_snapshot(
    *,
    firm_id: str,
    user_id: str,
    user_name: Optional[str],
    role_type: Optional[str],
    all_events: List[Dict[str, Any]],
    salary_snapshot: List[Dict[str, Any]],
    dispatcher_attribution: Dict[str, Any],
    as_of: datetime,
) -> Dict[str, Any]:
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
    period_cash_events = [
        item
        for item in all_events
        if _norm_text(item.get("event_type_upper")) == "CASH"
        and (lower_bound is None or _event_created_at(item) > lower_bound)
    ]

    period_salary_snapshot = _filter_salary_snapshot_for_current_period(
        salary_snapshot=salary_snapshot,
        lower_bound=lower_bound,
        as_of=as_of,
    )

    # Salary CASH still reduces the selected period rows by salary_id across
    # the full history up to as_of, but the visible salary window itself is
    # bounded by the latest accrual and does not pull future payout rows in.
    all_cash_summary = _collect_cash_finance_summary(all_events)
    period_cash_summary = _collect_cash_finance_summary(period_cash_events)
    salary_summary = _build_salary_balance_summary(
        salary_snapshot=period_salary_snapshot,
        salary_paid_by_id=all_cash_summary.get("salary_paid_by_id") or {},
    )

    cash = period_cash_summary.get("cash_events") or []
    rewards_fines_paid_kopeks = (
        _safe_int(period_cash_summary.get("rewards_fines_paid_kopeks"), 0) or 0
    )

    payable_salary_snapshot: List[Dict[str, Any]] = []
    for salary_item in salary_summary.get("salary_items") or []:
        if not isinstance(salary_item, dict):
            continue
        normalized_item = dict(salary_item)
        normalized_item["amount_kopeks"] = (
            _safe_int(normalized_item.get("remaining_kopeks"), 0) or 0
        )
        payable_salary_snapshot.append(normalized_item)

    salary_total_kopeks = (
        _safe_int(salary_summary.get("salary_total_remaining_kopeks"), 0) or 0
    )

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
            "attribution_type": dispatcher_attribution.get("attribution_type"),
            "percent_snapshot": dispatcher_attribution.get("percent_snapshot", 0.0),
            "created_at": dispatcher_attribution.get("created_at"),
            "updated_at": dispatcher_attribution.get("updated_at"),
        },
        "deferred_state": _extract_deferred_state(
            user_events=all_events,
            last_accrual=last_accrual,
            as_of=as_of,
        ),
        "employee_salary_snapshot": payable_salary_snapshot,
        "fines": fines,
        "rewards": rewards,
        "cash": cash,
        "shifts": shifts,
        "deals": deals,
        "withholds": withholds,
    }


def _build_month_preview(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    totals = snapshot.get("totals") if isinstance(snapshot.get("totals"), dict) else {}
    deferred_state = (
        snapshot.get("deferred_state")
        if isinstance(snapshot.get("deferred_state"), dict)
        else {}
    )
    employee_salary_snapshot = (
        snapshot.get("employee_salary_snapshot")
        if isinstance(snapshot.get("employee_salary_snapshot"), list)
        else []
    )
    return {
        "amount_kopeks": _safe_int(snapshot.get("amount_kopeks"), 0) or 0,
        "salary_total_remaining_kopeks": _safe_int(totals.get("salary_total_kopeks"), 0) or 0,
        "rewards_total_kopeks": _safe_int(totals.get("rewards_total_kopeks"), 0) or 0,
        "fines_total_kopeks": _safe_int(totals.get("fines_total_kopeks"), 0) or 0,
        "deals_total_kopeks": _safe_int(totals.get("deals_total_kopeks"), 0) or 0,
        "shifts_total_kopeks": _safe_int(totals.get("shifts_total_kopeks"), 0) or 0,
        "rewards_fines_paid_kopeks": _safe_int(totals.get("rewards_fines_paid_kopeks"), 0) or 0,
        "withholds_total_kopeks": _safe_int(totals.get("withholds_total_kopeks"), 0) or 0,
        "dispatcher_percent": float(
            (
                snapshot.get("dispatcher_attribution")
                if isinstance(snapshot.get("dispatcher_attribution"), dict)
                else {}
            ).get("percent_snapshot", 0.0)
            or 0.0
        ),
        "salary_items_count": len(employee_salary_snapshot),
        "events_total_count": _safe_int(totals.get("events_total_count"), 0) or 0,
        "period_started_at": snapshot.get("period_started_at"),
        "period_ended_at": snapshot.get("period_ended_at"),
        "is_deferred": bool(deferred_state.get("is_deferred")),
    }


def _parse_as_of(body: dict) -> Tuple[Optional[datetime], Optional[str]]:
    raw = body.get("as_of")
    if raw is None:
        return datetime.now(timezone.utc), None
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt, None
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day, 23, 59, 59, tzinfo=timezone.utc), None
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None, "as_of must be a valid ISO datetime"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt, None
    return None, "as_of must be a valid ISO datetime"


def _extract_cash_salary_payment_items(state: Any) -> List[Dict[str, Any]]:
    if not isinstance(state, dict):
        return []

    out: List[Dict[str, Any]] = []
    raw_items = state.get("salary_payment_items")
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            salary_id = _norm_text(item.get("salary_id"))
            amount_kopeks = _safe_int(item.get("amount_kopeks"))
            if not salary_id or amount_kopeks is None:
                continue
            out.append(
                {
                    "salary_id": salary_id,
                    "amount_kopeks": max(amount_kopeks, 0),
                }
            )
    if out:
        return out

    raw_components = state.get("payment_components")
    if not isinstance(raw_components, list):
        return out
    for component in raw_components:
        if not isinstance(component, dict):
            continue
        component_type = _norm_text(component.get("component_type")).lower()
        if component_type != "salary":
            continue
        salary_id = _norm_text(component.get("salary_id"))
        amount_kopeks = _safe_int(component.get("amount_kopeks"))
        if not salary_id or amount_kopeks is None:
            continue
        out.append(
            {
                "salary_id": salary_id,
                "amount_kopeks": max(amount_kopeks, 0),
            }
        )
    return out


def _extract_cash_rewards_fines_paid_kopeks(state: Any, amount_kopeks_fallback: Optional[int]) -> int:
    if not isinstance(state, dict):
        return 0

    raw_rewards_fines = state.get("rewards_fines_payment")
    if isinstance(raw_rewards_fines, dict):
        parsed = _safe_int(raw_rewards_fines.get("amount_kopeks"))
        if parsed is not None:
            return max(parsed, 0)

    direct_total = _safe_int(state.get("rewards_fines_total_kopeks"))
    if direct_total is not None:
        return max(direct_total, 0)

    payment_scope = _norm_text(state.get("payment_scope")).lower()
    if payment_scope == "rewards_fines" and isinstance(amount_kopeks_fallback, int):
        return max(abs(amount_kopeks_fallback), 0)

    return 0


def _collect_cash_finance_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    cash_events: List[Dict[str, Any]] = []
    salary_paid_by_id: Dict[str, int] = {}
    rewards_fines_paid_kopeks = 0

    for item in events:
        if _norm_text(item.get("event_type_upper")) != "CASH":
            continue
        cash_events.append(item)
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

    return {
        "cash_events": cash_events,
        "salary_paid_by_id": salary_paid_by_id,
        "rewards_fines_paid_kopeks": rewards_fines_paid_kopeks,
    }


def _build_salary_balance_summary(
    *,
    salary_snapshot: List[Dict[str, Any]],
    salary_paid_by_id: Dict[str, int],
) -> Dict[str, Any]:
    salary_items: List[Dict[str, Any]] = []
    salary_total_kopeks = 0
    salary_paid_kopeks = 0
    salary_total_remaining_kopeks = 0
    salary_total_overpaid_kopeks = 0
    active_salary_items_count = 0
    snapshot_salary_ids: Set[str] = set()

    for salary in salary_snapshot:
        if not isinstance(salary, dict):
            continue
        salary_id = _norm_text(salary.get("salary_id"))
        if not salary_id:
            continue
        snapshot_salary_ids.add(salary_id)
        normalized_item = dict(salary)
        source_amount_kopeks = max(_safe_int(normalized_item.get("amount_kopeks"), 0) or 0, 0)
        paid_kopeks = max(salary_paid_by_id.get(salary_id, 0), 0)
        remaining_kopeks = max(source_amount_kopeks - paid_kopeks, 0)
        overpaid_kopeks = max(paid_kopeks - source_amount_kopeks, 0)

        normalized_item["source_amount_kopeks"] = source_amount_kopeks
        normalized_item["paid_kopeks"] = paid_kopeks
        normalized_item["remaining_kopeks"] = remaining_kopeks
        normalized_item["overpaid_kopeks"] = overpaid_kopeks
        normalized_item["amount_kopeks"] = source_amount_kopeks
        salary_items.append(normalized_item)

        salary_total_kopeks += source_amount_kopeks
        salary_paid_kopeks += paid_kopeks
        salary_total_remaining_kopeks += remaining_kopeks
        salary_total_overpaid_kopeks += overpaid_kopeks
        active_salary_items_count += 1

    salary_paid_without_snapshot_kopeks = 0
    salary_paid_unknown_items: List[Dict[str, Any]] = []
    for salary_id, paid_kopeks in sorted(salary_paid_by_id.items()):
        if salary_id in snapshot_salary_ids:
            continue
        paid_norm = max(_safe_int(paid_kopeks, 0) or 0, 0)
        if paid_norm <= 0:
            continue
        salary_paid_without_snapshot_kopeks += paid_norm
        salary_paid_unknown_items.append(
            {
                "salary_id": salary_id,
                "paid_kopeks": paid_norm,
            }
        )

    return {
        "salary_items": salary_items,
        "salary_total_kopeks": salary_total_kopeks,
        "salary_paid_kopeks": salary_paid_kopeks,
        "salary_total_remaining_kopeks": salary_total_remaining_kopeks,
        "salary_total_overpaid_kopeks": salary_total_overpaid_kopeks,
        "active_salary_items_count": active_salary_items_count,
        "salary_paid_without_snapshot_kopeks": salary_paid_without_snapshot_kopeks,
        "salary_paid_unknown_items": salary_paid_unknown_items,
    }


def _collect_employee_events(
    *,
    event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
    user_id: str,
) -> List[Dict[str, Any]]:
    normalized_user_id = _norm_text(user_id)
    out: List[Dict[str, Any]] = []

    for row in event_rows:
        event_id = _norm_text(row.get("event_id"))
        if not event_id:
            continue

        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue

        event_user_id = _extract_state_user_id(state)
        if event_user_id != normalized_user_id:
            continue

        amount_kopeks = extract_amount_kopeks(state)
        if amount_kopeks is None:
            amount_kopeks = _extract_amount_fallback_kopeks(state)

        event_type = _norm_text(row.get("event_type"))
        event_type_upper = event_type.upper()

        out.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "event_type_upper": event_type_upper,
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "state": state,
                "amount_kopeks": amount_kopeks,
                "object_id": _extract_object_id(state),
            }
        )

    out.sort(
        key=lambda item: _event_sort_key(item),
        reverse=True,
    )
    return out


def _calc_totals(events: List[Dict[str, Any]]) -> Dict[str, int]:
    paid = 0
    pending = 0
    with_amount_count = 0

    for item in events:
        amount_kopeks = item.get("amount_kopeks")
        if not isinstance(amount_kopeks, int):
            continue
        amount_abs = abs(amount_kopeks)
        if amount_abs == 0:
            continue
        with_amount_count += 1

        event_type_upper = _norm_text(item.get("event_type_upper"))
        if event_type_upper in PAID_TYPES:
            paid += amount_abs
            pending -= amount_abs
            continue

        if event_type_upper in NEGATIVE_PENDING_TYPES:
            pending -= amount_abs
        else:
            pending += amount_abs

    return {
        "paid_kopeks": paid,
        "pending_kopeks": pending,
        "events_with_amount_count": with_amount_count,
    }


def _build_response_events(
    *,
    events: List[Dict[str, Any]],
    objects_map: Dict[str, Dict[str, Any]],
    fine_disputes_by_event_id: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in events:
        event_id = _norm_text(item.get("event_id"))
        event_type_upper = _norm_text(item.get("event_type_upper"))
        object_id = _norm_text(item.get("object_id"))
        object_info = objects_map.get(object_id) if object_id else None

        disputes = (
            fine_disputes_by_event_id.get(event_id, [])
            if event_type_upper == "FINE"
            else []
        )
        dispute_summary = _to_fine_dispute_summary(disputes)
        latest_dispute = (
            dispute_summary.get("latest_dispute")
            if isinstance(dispute_summary, dict)
            else None
        )
        dispute_appeal_id = (
            _norm_text(latest_dispute.get("appeal_id"))
            if isinstance(latest_dispute, dict)
            else ""
        )

        out.append(
            {
                "event_id": event_id,
                "event_type": _norm_text(item.get("event_type")),
                "created_at": _to_iso_utc(item.get("created_at")),
                "updated_at": _to_iso_utc(item.get("updated_at")),
                "amount_kopeks": item.get("amount_kopeks"),
                "state": item.get("state") if isinstance(item.get("state"), dict) else {},
                "object_id": object_id or None,
                "object": object_info,
                "dispute_appeal_id": dispute_appeal_id or None,
                "dispute": dispute_summary,
            }
        )
    return out


def handle_employee_finance_month_list(
    body,
    firm_id,
    events_pool,
    events_database,
    notices_pool,
    notices_database,
    objects_pool,
    objects_database,
    appeals_pool,
    appeals_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_finance_month_list.start", firm_id=firm_id)

    user_id = _norm_text(body.get("user_id"))
    if not user_id:
        return bad_request("user_id is required")

    month, year, period_error = _parse_month_year(body)
    if period_error:
        return bad_request(period_error)

    page, page_size, page_error = _parse_page(body)
    if page_error:
        return bad_request(page_error)

    try:
        start, end = _month_range(year=year, month=month)
        month_event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start,
            end=end,
        )
        snapshot_as_of = _resolve_period_as_of(end)
        snapshot_event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end=snapshot_as_of + timedelta(seconds=1),
        )

        event_ids = [
            row["event_id"]
            for row in [*month_event_rows, *snapshot_event_rows]
            if _norm_text(row.get("event_id"))
        ]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )

        employee_month_events = _collect_employee_events(
            event_rows=month_event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        employee_snapshot_events = _collect_employee_events(
            event_rows=snapshot_event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        work_item_amount_context = _build_work_item_amount_context(
            events=[*employee_month_events, *employee_snapshot_events],
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        employee_month_events = _enrich_work_item_amounts(
            events=employee_month_events,
            amount_context=work_item_amount_context,
            logger=logger,
        )
        employee_snapshot_events = _enrich_work_item_amounts(
            events=employee_snapshot_events,
            amount_context=work_item_amount_context,
            logger=logger,
        )
        month_totals = _calc_totals(employee_month_events)
        salary_snapshot = _read_employee_salary_snapshot(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            user_id=user_id,
            as_of=snapshot_as_of,
        )
        dispatcher_attribution = _read_dispatcher_attribution(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            user_id=user_id,
        )
        current_snapshot = _build_current_finance_snapshot(
            firm_id=firm_id,
            user_id=user_id,
            user_name=None,
            role_type=None,
            all_events=employee_snapshot_events,
            salary_snapshot=salary_snapshot,
            dispatcher_attribution=dispatcher_attribution,
            as_of=snapshot_as_of,
        )

        total = len(employee_month_events)
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total)
        page_items = employee_month_events[start_idx:end_idx] if start_idx < total else []

        object_ids = [_norm_text(item.get("object_id")) for item in page_items if _norm_text(item.get("object_id"))]
        objects_map = _read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_id,
            object_ids=object_ids,
        )
        fine_event_ids = [
            _norm_text(item.get("event_id"))
            for item in page_items
            if _norm_text(item.get("event_type_upper")) == "FINE"
            and _norm_text(item.get("event_id"))
        ]
        fine_disputes_by_event_id = _read_fine_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_id,
            event_ids=fine_event_ids,
        )

        response_events = _build_response_events(
            events=page_items,
            objects_map=objects_map,
            fine_disputes_by_event_id=fine_disputes_by_event_id,
        )
        dispatcher_percent = dispatcher_attribution.get("percent_snapshot", 0.0)

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        has_prev = page > 0 and total > 0
        has_next = end_idx < total

        logger.info(
            "analytics_getter.employee_finance_month_list.success",
            firm_id=firm_id,
            user_id=user_id,
            month=month,
            year=year,
            total=total,
            page=page,
            page_size=page_size,
            page_items=len(response_events),
            month_pending_kopeks=month_totals["pending_kopeks"],
            current_pending_kopeks=current_snapshot["amount_kopeks"],
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev,
                "events_count": total,
                "dispatcher_percent": dispatcher_percent,
                "total_paid_kopeks": month_totals["paid_kopeks"],
                "total_pending_kopeks": current_snapshot["amount_kopeks"],
                "month_preview": _build_month_preview(current_snapshot),
                "finance_events": response_events,
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_month_list.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_month_list.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_finance_month_total(
    body,
    firm_id,
    events_pool,
    events_database,
    notices_pool,
    notices_database,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_finance_month_total.start", firm_id=firm_id)

    user_id = _norm_text(body.get("user_id"))
    if not user_id:
        return bad_request("user_id is required")

    month, year, period_error = _parse_month_year(body)
    if period_error:
        return bad_request(period_error)

    try:
        start, end = _month_range(year=year, month=month)
        month_event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start,
            end=end,
        )
        snapshot_as_of = _resolve_period_as_of(end)
        snapshot_event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end=snapshot_as_of + timedelta(seconds=1),
        )

        event_ids = [
            row["event_id"]
            for row in [*month_event_rows, *snapshot_event_rows]
            if _norm_text(row.get("event_id"))
        ]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )

        employee_month_events = _collect_employee_events(
            event_rows=month_event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        employee_snapshot_events = _collect_employee_events(
            event_rows=snapshot_event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        work_item_amount_context = _build_work_item_amount_context(
            events=[*employee_month_events, *employee_snapshot_events],
            firm_id=firm_id,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        employee_month_events = _enrich_work_item_amounts(
            events=employee_month_events,
            amount_context=work_item_amount_context,
            logger=logger,
        )
        employee_snapshot_events = _enrich_work_item_amounts(
            events=employee_snapshot_events,
            amount_context=work_item_amount_context,
            logger=logger,
        )
        month_totals = _calc_totals(employee_month_events)
        salary_snapshot = _read_employee_salary_snapshot(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            user_id=user_id,
            as_of=snapshot_as_of,
        )
        dispatcher_attribution = _read_dispatcher_attribution(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            user_id=user_id,
        )
        current_snapshot = _build_current_finance_snapshot(
            firm_id=firm_id,
            user_id=user_id,
            user_name=None,
            role_type=None,
            all_events=employee_snapshot_events,
            salary_snapshot=salary_snapshot,
            dispatcher_attribution=dispatcher_attribution,
            as_of=snapshot_as_of,
        )
        dispatcher_percent = dispatcher_attribution.get("percent_snapshot", 0.0)

        logger.info(
            "analytics_getter.employee_finance_month_total.success",
            firm_id=firm_id,
            user_id=user_id,
            month=month,
            year=year,
            events_count=len(employee_month_events),
            paid_kopeks=month_totals["paid_kopeks"],
            month_pending_kopeks=month_totals["pending_kopeks"],
            current_pending_kopeks=current_snapshot["amount_kopeks"],
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "events_count": len(employee_month_events),
                "events_with_amount_count": month_totals["events_with_amount_count"],
                "dispatcher_percent": dispatcher_percent,
                "total_paid_kopeks": month_totals["paid_kopeks"],
                "total_pending_kopeks": current_snapshot["amount_kopeks"],
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_month_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_month_total.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_finance_total(
    body,
    firm_id,
    events_pool,
    events_database,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_finance_total.start", firm_id=firm_id)

    user_id = _norm_text(body.get("user_id"))
    if not user_id:
        return bad_request("user_id is required")

    year = _safe_int(body.get("year"), datetime.now(timezone.utc).year)
    if year is None or year < 2020 or year > 2100:
        return bad_request("year must be an integer between 2020 and 2100")

    try:
        start, end = _year_range(year=year)
        event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start,
            end=end,
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
        totals = _calc_totals(employee_events)
        dispatcher_percent = _read_dispatcher_percent(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            user_id=user_id,
        )

        logger.info(
            "analytics_getter.employee_finance_total.success",
            firm_id=firm_id,
            user_id=user_id,
            year=year,
            events_count=len(employee_events),
            paid_kopeks=totals["paid_kopeks"],
            pending_kopeks=totals["pending_kopeks"],
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "year": year,
                "events_count": len(employee_events),
                "events_with_amount_count": totals["events_with_amount_count"],
                "dispatcher_percent": dispatcher_percent,
                "total_paid_kopeks": totals["paid_kopeks"],
                "total_pending_kopeks": totals["pending_kopeks"],
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_total.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_finance_cash_plan(
    body,
    firm_id,
    events_pool,
    events_database,
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
        salary_snapshot = _read_employee_salary_snapshot(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            user_id=user_id,
            as_of=as_of,
        )

        rewards_fines_created_kopeks = 0

        for item in employee_events:
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

        cash_summary = _collect_cash_finance_summary(employee_events)
        rewards_fines_paid_kopeks = (
            _safe_int(cash_summary.get("rewards_fines_paid_kopeks"), 0) or 0
        )
        rewards_fines_balance_kopeks = rewards_fines_created_kopeks - rewards_fines_paid_kopeks
        rewards_fines_pending_kopeks = max(rewards_fines_balance_kopeks, 0)
        rewards_fines_overpaid_kopeks = max(-rewards_fines_balance_kopeks, 0)

        salary_summary = _build_salary_balance_summary(
            salary_snapshot=salary_snapshot,
            salary_paid_by_id=cash_summary.get("salary_paid_by_id") or {},
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

        total_to_cover_all_kopeks = rewards_fines_pending_kopeks + salary_total_remaining_kopeks

        logger.info(
            "analytics_getter.employee_finance_cash_plan.success",
            firm_id=firm_id,
            user_id=user_id,
            events_count=len(employee_events),
            salary_items_count=len(salary_items),
            rewards_fines_pending_kopeks=rewards_fines_pending_kopeks,
            salary_total_remaining_kopeks=salary_total_remaining_kopeks,
            total_to_cover_all_kopeks=total_to_cover_all_kopeks,
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
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_cash_plan.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_cash_plan.error", error=str(e))
        return server_error("Internal Server Error")
