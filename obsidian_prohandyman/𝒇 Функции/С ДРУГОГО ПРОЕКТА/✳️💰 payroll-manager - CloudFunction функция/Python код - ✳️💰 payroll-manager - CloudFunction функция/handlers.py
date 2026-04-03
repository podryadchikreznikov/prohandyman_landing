# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import traceback
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import ydb

from utils import (
    JsonLogger,
    bad_request,
    created,
    forbidden,
    not_found,
    ok,
    parse_iso_utc,
    server_error,
    now_utc,
)
from utils.util_log import YCLogger
from utils.util_metadata import parse_json_value

from common import is_uuid
from constants import ALLOWED_ROLE_TYPES, EVENT_ACCRUAL, EVENT_CASH, EVENT_DEFERRED, EVENT_FINE, EVENT_REWARD
from events_helper import create_event_entity
from internal_calls import call_metadata_validator
from notification_sender import send_notification


def _parse_iso_datetime(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        try:
            parse_iso_utc(value.strip())
            return value.strip()
        except Exception:
            return None
    return None


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, str) and value.strip():
        try:
            return date.fromisoformat(value.strip())
        except Exception:
            return None
    return None


def _parse_json_value(value: Any) -> Any:
    return parse_json_value(value)


def _validate_field_type(schema_name: str, value: Any, logger: JsonLogger) -> Any:
    try:
        return call_metadata_validator(schema_name, "field_type", value, logger)
    except ValueError as e:
        raise ValueError(str(e))


def ensure_caller_access(
    *,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    def _tx(session: ydb.Session) -> Dict[str, Any]:
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            SELECT role_type
            FROM firm_employees
            WHERE firm_id = $firm_id AND user_id = $user_id
            LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$user_id": caller_user_id},
            commit_tx=True,
        )
        if not rs or not rs[0].rows:
            return {"status": "NOT_FOUND"}
        role_type = str(rs[0].rows[0].role_type or "").lower()
        return {"status": "OK", "role_type": role_type}

    try:
        result = firms_pool.retry_operation_sync(_tx)
    except Exception as e:
        logger.error("payroll_manager.access.role_fetch_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.access.role_fetch_failed", error=str(e))
        return server_error("Internal Server Error")

    if result.get("status") == "NOT_FOUND":
        return forbidden("Access denied")
    role_type = result.get("role_type")
    if role_type not in ALLOWED_ROLE_TYPES:
        return forbidden("Access denied")
    return None


def _ensure_employee_exists(
    *,
    firm_id: str,
    user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
) -> Optional[dict]:
    active_statuses = {"active_unattached", "active_attached"}

    def _tx(session: ydb.Session) -> Dict[str, Any]:
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            SELECT user_id, status
            FROM firm_employees
            WHERE firm_id = $firm_id AND user_id = $user_id
            LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$user_id": user_id},
            commit_tx=True,
        )
        if not rs or not rs[0].rows:
            return {"status": "NOT_FOUND"}
        row = rs[0].rows[0]
        employee_status = str(getattr(row, "status", "") or "").lower()
        if employee_status not in active_statuses:
            return {"status": "INACTIVE"}
        return {"status": "OK"}

    try:
        result = firms_pool.retry_operation_sync(_tx)
    except Exception as e:
        logger.error("payroll_manager.employee_check_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.employee_check_failed", error=str(e))
        return server_error("Internal Server Error")

    if result.get("status") in ("NOT_FOUND", "INACTIVE"):
        return not_found("Employee not found")
    return None


def _format_money_kopeks(value: Any) -> str:
    try:
        amount = int(value or 0)
    except Exception:
        amount = 0
    rub = amount // 100
    kop = amount % 100
    rub_text = f"{rub:,}".replace(",", " ")
    return f"{rub_text},{kop:02d} ₽"


def _read_firm_name(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
) -> Optional[str]:
    out: Optional[str] = None

    def _tx(session: ydb.Session):
        nonlocal out
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            SELECT firm_name FROM Firms WHERE firm_id = $firm_id LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        if rs and rs[0].rows:
            out = str(getattr(rs[0].rows[0], "firm_name", "") or "").strip() or None

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_user_full_name(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    user_id: str,
) -> Optional[str]:
    out: Optional[str] = None

    def _tx(session: ydb.Session):
        nonlocal out
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $user_id AS Utf8;
            SELECT full_name FROM UserProfiles WHERE user_id = $user_id LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$user_id": user_id},
            commit_tx=True,
        )
        if rs and rs[0].rows:
            out = str(getattr(rs[0].rows[0], "full_name", "") or "").strip() or None

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_supervisor_ids(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
) -> List[str]:
    out: List[str] = []
    seen = set()
    allowed_roles = {"owner", "admin", "manager", "foreman", "foreman_foreman"}

    def _tx(session: ydb.Session):
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            SELECT user_id, role_type, status
            FROM firm_employees
            WHERE firm_id = $firm_id;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            user_id = str(getattr(row, "user_id", "") or "").strip()
            role_type = str(getattr(row, "role_type", "") or "").strip().lower()
            status = str(getattr(row, "status", "") or "").strip().lower()
            if not user_id or role_type not in allowed_roles or not status.startswith("active"):
                continue
            if user_id in seen:
                continue
            seen.add(user_id)
            out.append(user_id)

    firms_pool.retry_operation_sync(_tx)
    return out


def _send_notice_safe(
    *,
    logger: JsonLogger,
    hlog: YCLogger,
    user_id: Optional[str],
    notice_type: str,
    data: Dict[str, Any],
) -> None:
    uid = str(user_id or "").strip()
    if not uid:
        return
    send_notification(
        logger=logger,
        hlog=hlog,
        user_id_to_notify=uid,
        notice_type=notice_type,
        data=data,
    )


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
    text = str(value).strip()
    if not text:
        return None
    return text


def _to_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        return None
    return text


def _server_now_iso() -> str:
    server_now = _to_iso_utc(now_utc())
    if server_now is None:
        raise ValueError("now_utc returned empty value")
    return server_now


CURRENT_SOURCE_EVENT_TYPES = {
    "REWARD",
    "FINE",
    "SHIFT_END",
    "DEAL_COMPLETE",
}

_ACCRUAL_RELEVANT_EVENT_TYPES_SQL = ", ".join(
    [
        f"'{value}'"
        for value in sorted(
            {
                normalized
                for raw in (
                    "accrual",
                    "cash",
                    "deferred",
                    *[value.lower() for value in CURRENT_SOURCE_EVENT_TYPES],
                )
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


def _chunked(values: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        return [values]
    return [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]


def _extract_user_id_from_state(state: Any) -> str:
    if not isinstance(state, dict):
        return ""
    for key in ("user_id", "worker_user_id", "worker_id", "employee_id"):
        value = _norm_text(state.get(key))
        if value:
            return value
    for key in ("completed_by", "assigned_by", "canceled_by"):
        value = _norm_text(state.get(key))
        if value:
            return value
    metadata = state.get("metadata")
    if isinstance(metadata, dict):
        for key in ("user_id", "worker_user_id", "worker_id", "employee_id"):
            value = _norm_text(metadata.get(key))
            if value:
                return value
    return ""


def _extract_amount_kopeks_from_state(state: Any) -> Optional[int]:
    if not isinstance(state, dict):
        return None
    for key in (
        "amount_kopeks",
        "withhold_amount_kopeks",
        "withheld_kopeks",
        "withholding_kopeks",
    ):
        value = state.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                try:
                    return int(text)
                except Exception:
                    pass

    amount_fallback = state.get("amount")
    if isinstance(amount_fallback, int):
        return amount_fallback
    if isinstance(amount_fallback, float) and amount_fallback.is_integer():
        return int(amount_fallback)
    if isinstance(amount_fallback, str):
        text = amount_fallback.strip()
        if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            try:
                return int(text)
            except Exception:
                return None
    return None


def _read_finance_event_rows(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    start_at: datetime,
    end_at: datetime,
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
              AND event_type IN ({_ACCRUAL_RELEVANT_EVENT_TYPES_SQL})
              AND created_at >= $start_at
              AND created_at < $end_at
            ORDER BY sequence_number ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": start_at, "$end_at": end_at},
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
    logger: JsonLogger,
) -> Dict[str, dict]:
    if not event_ids:
        return {}

    out: Dict[str, dict] = {}

    def _read_chunk(session: ydb.Session, ids: List[str]) -> None:
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
            parsed_state = parse_json_value(getattr(row, "state_json", None))
            if isinstance(parsed_state, dict):
                out[event_id] = parsed_state

    for chunk in _chunked(event_ids, 200):
        try:
            meta_pool.retry_operation_sync(lambda session, ids=chunk: _read_chunk(session, ids))
        except Exception as e:
            logger.error("payroll_manager.meta.fetch_state_failed", error=str(e), trace=traceback.format_exc())
            raise

    return out


def _event_created_at(item: Dict[str, Any]) -> datetime:
    value = item.get("created_at")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _event_sort_key(item: Dict[str, Any]) -> Tuple[datetime, str]:
    return (_event_created_at(item), _norm_text(item.get("event_id")))


def _latest_event_of_type(events: List[Dict[str, Any]], event_type_upper: str) -> Optional[Dict[str, Any]]:
    latest: Optional[Dict[str, Any]] = None
    for item in events:
        if _norm_text(item.get("event_type_upper")) != event_type_upper:
            continue
        if latest is None or _event_sort_key(item) > _event_sort_key(latest):
            latest = item
    return latest


def _sum_amounts(events: List[Dict[str, Any]]) -> int:
    total = 0
    for item in events:
        amount_kopeks = item.get("amount_kopeks")
        if isinstance(amount_kopeks, int):
            total += abs(amount_kopeks)
    return total


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


def _extract_accrual_link(event: Optional[Dict[str, Any]]) -> str:
    if not isinstance(event, dict):
        return ""
    state = event.get("state")
    if not isinstance(state, dict):
        return ""
    return _norm_text(state.get("accrual_event_id"))


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


def _extract_cash_rewards_fines_paid_kopeks(
    state: Any,
    amount_kopeks_fallback: Optional[int],
) -> int:
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


def _collect_user_finance_events(
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

        event_user_id = _extract_user_id_from_state(state)
        if event_user_id != normalized_user_id:
            continue

        out.append(
            {
                "event_id": event_id,
                "event_type": _norm_text(row.get("event_type")),
                "event_type_upper": _norm_text(row.get("event_type")).upper(),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "state": state,
                "amount_kopeks": _extract_amount_kopeks_from_state(state),
            }
        )

    out.sort(key=_event_sort_key, reverse=True)
    return out


def _read_employee_role_type(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    user_id: str,
) -> Optional[str]:
    out: Optional[str] = None

    def _tx(session: ydb.Session):
        nonlocal out
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            SELECT role_type
            FROM firm_employees
            WHERE firm_id = $firm_id AND user_id = $user_id
            LIMIT 1;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$user_id": user_id},
            commit_tx=True,
        )
        if rs and rs[0].rows:
            out = _norm_text(getattr(rs[0].rows[0], "role_type", None)).lower() or None

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_dispatcher_attribution_for_user(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    user_id: str,
) -> Dict[str, Any]:
    out = {
        "dispatcher_id": None,
        "percent_snapshot": 0.0,
        "created_at": None,
        "updated_at": None,
    }

    def _tx(session: ydb.Session):
        nonlocal out
        q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            SELECT worker_user_id, dispatcher_id, percent_snapshot, created_at, updated_at
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
        row = rows[0]
        percent_snapshot = getattr(row, "percent_snapshot", None)
        try:
            percent_snapshot = float(percent_snapshot or 0.0)
        except Exception:
            percent_snapshot = 0.0
        out = {
            "dispatcher_id": _norm_text(getattr(row, "dispatcher_id", None)) or None,
            "percent_snapshot": percent_snapshot,
            "created_at": _to_iso_utc(getattr(row, "created_at", None)),
            "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
        }

    firms_pool.retry_operation_sync(_tx)
    return out


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
        if event_type_upper != "DEFERRED":
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


def _build_accrual_queue_item(
    *,
    firm_id: str,
    user_id: str,
    user_name: Optional[str],
    salary_snapshot: List[Dict[str, Any]],
    user_events: List[Dict[str, Any]],
    dispatcher_attribution: Dict[str, Any],
    as_of: datetime,
) -> Dict[str, Any]:
    last_accrual = _latest_event_of_type(user_events, "ACCRUAL")
    period_started_at = _to_iso_utc(last_accrual.get("created_at")) if isinstance(last_accrual, dict) else None
    lower_bound = _event_created_at(last_accrual) if isinstance(last_accrual, dict) else None
    dispatcher_percent_snapshot = dispatcher_attribution.get("percent_snapshot", 0.0)

    pending_events: List[Dict[str, Any]] = []
    for item in user_events:
        if _norm_text(item.get("event_type_upper")) not in CURRENT_SOURCE_EVENT_TYPES:
            continue
        if lower_bound is not None and _event_created_at(item) <= lower_bound:
            continue
        pending_events.append(item)

    fines = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "FINE"]
    rewards = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "REWARD"]
    shifts = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "SHIFT_END"]
    deals = [item for item in pending_events if _norm_text(item.get("event_type_upper")) == "DEAL_COMPLETE"]
    withholds: List[Dict[str, Any]] = []

    salary_paid_by_id: Dict[str, int] = {}
    rewards_fines_paid_kopeks = 0
    for item in user_events:
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
    shifts_total_kopeks = _sum_amounts_after_dispatcher_withhold(
        shifts,
        percent_snapshot=dispatcher_percent_snapshot,
    )
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

    deferred_state_raw = _extract_deferred_state(
        user_events=user_events,
        last_accrual=last_accrual,
        as_of=as_of,
    )

    dispatcher_payload: Dict[str, Any] = {
        "percent_snapshot": dispatcher_attribution.get("percent_snapshot", 0.0),
    }
    dispatcher_id = dispatcher_attribution.get("dispatcher_id")
    if isinstance(dispatcher_id, str) and dispatcher_id.strip():
        dispatcher_payload["dispatcher_id"] = dispatcher_id
    created_at = dispatcher_attribution.get("created_at")
    if isinstance(created_at, str) and created_at.strip():
        dispatcher_payload["created_at"] = created_at
    updated_at = dispatcher_attribution.get("updated_at")
    if isinstance(updated_at, str) and updated_at.strip():
        dispatcher_payload["updated_at"] = updated_at

    deferred_payload: Dict[str, Any] = {
        "is_deferred": bool(deferred_state_raw.get("is_deferred")),
    }
    for key in ("deferred_until", "deferred_event_id", "accrual_event_id", "event_at"):
        raw_value = deferred_state_raw.get(key)
        if isinstance(raw_value, str) and raw_value.strip():
            deferred_payload[key] = raw_value

    payload = {
        "firm_id": firm_id,
        "user_id": user_id,
        "user_name": user_name,
        "amount_kopeks": amount_kopeks,
        "period_ended_at": _to_iso_utc(as_of),
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
        "dispatcher_attribution": dispatcher_payload,
        "deferred_state": deferred_payload,
        "employee_salary_snapshot": payable_salary_snapshot,
        "fines": fines,
        "rewards": rewards,
        "shifts": shifts,
        "deals": deals,
        "withholds": withholds,
    }

    if isinstance(period_started_at, str) and period_started_at.strip():
        payload["period_started_at"] = period_started_at
        payload["source_last_accrual_created_at"] = period_started_at

    source_last_accrual_event_id = _norm_text(last_accrual.get("event_id")) or None if isinstance(last_accrual, dict) else None
    if source_last_accrual_event_id:
        payload["source_last_accrual_event_id"] = source_last_accrual_event_id

    return payload


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


def _read_employee_salary_snapshot(
    *,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    firm_id: str,
    user_id: str,
    active_only: bool = False,
    as_of: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        where_parts = [
            "firm_id = $firm_id",
            "user_id = $user_id",
        ]
        if as_of:
            where_parts.append("(effective_from IS NULL OR effective_from <= $as_of)")
            where_parts.append("(deleted_at IS NULL OR deleted_at > $as_of)")
        elif active_only:
            where_parts.append('(status = "active" AND deleted_at IS NULL)')
        q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            {"DECLARE $as_of AS Timestamp;" if as_of else ""}
            SELECT salary_id, user_id, firm_id, amount, payout_date, last_payout_at, status, effective_from, deleted_at, created_at, updated_at
            FROM employee_salary
            WHERE {" AND ".join(where_parts)}
            ORDER BY payout_date ASC, effective_from ASC, deleted_at ASC, created_at ASC;
        """
        params = {"$firm_id": firm_id, "$user_id": user_id}
        if as_of:
            params["$as_of"] = parse_iso_utc(as_of)
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            params,
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            salary_id = str(getattr(row, "salary_id", "") or "").strip()
            if not salary_id:
                continue
            out.append(
                {
                    "salary_id": salary_id,
                    "user_id": str(getattr(row, "user_id", "") or "").strip() or user_id,
                    "firm_id": str(getattr(row, "firm_id", "") or "").strip() or firm_id,
                    "amount_kopeks": int(getattr(row, "amount", 0) or 0),
                    "payout_date": _to_iso_date(getattr(row, "payout_date", None)),
                    "last_payout_at": _to_iso_utc(getattr(row, "last_payout_at", None)),
                    "status": str(getattr(row, "status", "") or "").strip().lower() or "active",
                    "effective_from": _to_iso_utc(getattr(row, "effective_from", None)),
                    "deleted_at": _to_iso_utc(getattr(row, "deleted_at", None)),
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }
            )

    notices_pool.retry_operation_sync(_tx)
    return out


def _update_salary_last_payout_at(
    *,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    firm_id: str,
    salary_payment_items: List[Dict[str, Any]],
):
    latest_paid_at_by_salary_id: Dict[str, datetime] = {}
    for item in salary_payment_items:
        salary_id = str(item.get("salary_id") or "").strip()
        paid_at_raw = _parse_iso_datetime(item.get("paid_at"))
        if not salary_id or not paid_at_raw:
            continue
        paid_at = parse_iso_utc(paid_at_raw)
        current_latest = latest_paid_at_by_salary_id.get(salary_id)
        if current_latest is None or paid_at > current_latest:
            latest_paid_at_by_salary_id[salary_id] = paid_at

    if not latest_paid_at_by_salary_id:
        return

    def _tx(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())
        tx.begin()
        q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $last_payout_at AS Timestamp;
            UPDATE employee_salary
            SET last_payout_at = $last_payout_at
            WHERE salary_id = $salary_id AND firm_id = $firm_id;
        """
        prepared = session.prepare(q)
        for salary_id, paid_at in latest_paid_at_by_salary_id.items():
            tx.execute(
                prepared,
                {
                    "$salary_id": salary_id,
                    "$firm_id": firm_id,
                    "$last_payout_at": paid_at,
                },
            )
        tx.commit()

    notices_pool.retry_operation_sync(_tx)


def _build_salary_change_notice_data(
    *,
    firm_id: str,
    user_id: str,
    firm_name: str,
    salary_snapshot: List[Dict[str, Any]],
    effective_from: Optional[str],
    action_text: str,
    status_text: str,
) -> Dict[str, Any]:
    active_records_count = 0
    deleted_records_count = 0
    for item in salary_snapshot:
        status = str(item.get("status", "") or "").strip().lower()
        if status == "deleted":
            deleted_records_count += 1
        else:
            active_records_count += 1

    return {
        "firm_id": firm_id,
        "firm_name": firm_name,
        "user_id": user_id,
        "salary_text": "Изменен график заработной платы",
        "employee_salary_snapshot": salary_snapshot,
        "effective_from": effective_from,
        "action_text": action_text,
        "status_text": status_text,
        "active_records_count": active_records_count,
        "deleted_records_count": deleted_records_count,
    }


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


def handle_salary_upsert(
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
    salary_id = body.get("salary_id")
    user_id = body.get("user_id")
    amount_kopeks = body.get("amount_kopeks")
    payout_date_raw = body.get("payout_date")
    effective_from_raw = body.get("effective_from")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not isinstance(amount_kopeks, int) or amount_kopeks < 0:
        return bad_request("amount_kopeks must be a non-negative integer")

    payout_date = _parse_date(payout_date_raw)
    if not payout_date:
        return bad_request("payout_date must be a valid date (YYYY-MM-DD)")
    effective_from = _parse_iso_datetime(effective_from_raw)
    if not effective_from:
        return bad_request("effective_from must be a valid ISO datetime")

    user_id = user_id.strip()
    salary_id = salary_id.strip() if isinstance(salary_id, str) and salary_id.strip() else None
    if salary_id and not is_uuid(salary_id):
        return bad_request("salary_id must be a valid UUID")

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

    now = now_utc()

    def _tx(session: ydb.Session) -> Dict[str, Any]:
        tx = session.transaction(ydb.SerializableReadWrite())

        if salary_id:
            select_q = f"""
                PRAGMA TablePathPrefix('{notices_database}');
                DECLARE $salary_id AS Utf8;
                DECLARE $firm_id AS Utf8;
                SELECT salary_id
                FROM employee_salary
                WHERE salary_id = $salary_id AND firm_id = $firm_id
                LIMIT 1;
            """
            rs = tx.execute(session.prepare(select_q), {"$salary_id": salary_id, "$firm_id": firm_id})
            if not rs or not rs[0].rows:
                tx.rollback()
                return {"status": "NOT_FOUND"}

            update_q = f"""
                PRAGMA TablePathPrefix('{notices_database}');
                DECLARE $salary_id AS Utf8;
                DECLARE $firm_id AS Utf8;
                DECLARE $amount AS Int64;
                DECLARE $payout_date AS Date;
                DECLARE $effective_from AS Timestamp;
                DECLARE $updated_at AS Timestamp;
                UPDATE employee_salary
                SET amount = $amount, payout_date = $payout_date, status = "active", effective_from = $effective_from, deleted_at = NULL, updated_at = $updated_at
                WHERE salary_id = $salary_id AND firm_id = $firm_id;
            """
            tx.execute(
                session.prepare(update_q),
                {
                    "$salary_id": salary_id,
                    "$firm_id": firm_id,
                    "$amount": amount_kopeks,
                    "$payout_date": payout_date,
                    "$effective_from": parse_iso_utc(effective_from),
                    "$updated_at": now,
                },
            )
            tx.commit()
            return {"status": "UPDATED", "salary_id": salary_id}

        new_salary_id = str(uuid.uuid4())
        insert_q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $amount AS Int64;
            DECLARE $payout_date AS Date;
            DECLARE $effective_from AS Timestamp;
            DECLARE $created_at AS Timestamp;
            DECLARE $updated_at AS Timestamp;
            UPSERT INTO employee_salary (
                salary_id,
                user_id,
                firm_id,
                amount,
                payout_date,
                last_payout_at,
                status,
                effective_from,
                deleted_at,
                created_at,
                updated_at
            ) VALUES (
                $salary_id,
                $user_id,
                $firm_id,
                $amount,
                $payout_date,
                NULL,
                "active",
                $effective_from,
                NULL,
                $created_at,
                $updated_at
            );
        """
        tx.execute(
            session.prepare(insert_q),
            {
                "$salary_id": new_salary_id,
                "$user_id": user_id,
                "$firm_id": firm_id,
                "$amount": amount_kopeks,
                "$payout_date": payout_date,
                "$effective_from": parse_iso_utc(effective_from),
                "$created_at": now,
                "$updated_at": now,
            },
        )
        tx.commit()
        return {"status": "CREATED", "salary_id": new_salary_id}

    try:
        result = notices_pool.retry_operation_sync(_tx)
    except Exception as e:
        logger.error("payroll_manager.salary_upsert.tx_error", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.salary_upsert.tx_error", error=str(e))
        return server_error("Internal Server Error")

    if result.get("status") == "NOT_FOUND":
        return not_found("Salary record not found")

    try:
        logger.info(
            "payroll_manager.salary_upsert.notice_start",
            firm_id=firm_id,
            user_id=user_id,
            salary_id=result.get("salary_id"),
            amount_kopeks=amount_kopeks,
        )
        notice_result = _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="your_salary_changed",
            data=_build_salary_change_notice_data(
                firm_id=firm_id,
                user_id=user_id,
                firm_name=_read_firm_name(
                    firms_pool=firms_pool,
                    firms_database=firms_database,
                    firm_id=firm_id,
                )
                or f"Фирма {firm_id}",
                salary_snapshot=_read_employee_salary_snapshot(
                    notices_pool=notices_pool,
                    notices_database=notices_database,
                    firm_id=firm_id,
                    user_id=user_id,
                ),
                effective_from=effective_from,
                action_text="Запись зарплаты сохранена",
                status_text="active",
            ),
        )
        logger.info(
            "payroll_manager.salary_upsert.notice_done",
            firm_id=firm_id,
            user_id=user_id,
            salary_id=result.get("salary_id"),
            notice_result=notice_result,
        )
    except Exception as e:
        logger.error("payroll_manager.salary_upsert.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.salary_upsert.notice_failed", error=str(e))

    return ok(
        {
            "message": "Salary saved",
            "firm_id": firm_id,
            "salary_id": result.get("salary_id"),
            "user_id": user_id,
        }
    )


def handle_salary_delete(
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
    salary_id = body.get("salary_id")
    user_id = body.get("user_id")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not isinstance(salary_id, str) or not salary_id.strip():
        return bad_request("salary_id is required")
    if not is_uuid(salary_id.strip()):
        return bad_request("salary_id must be a valid UUID")

    user_id = user_id.strip()
    salary_id = salary_id.strip()

    def _tx(session: ydb.Session) -> Dict[str, Any]:
        tx = session.transaction(ydb.SerializableReadWrite())

        select_q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            SELECT salary_id
            FROM employee_salary
            WHERE salary_id = $salary_id AND firm_id = $firm_id AND user_id = $user_id
            LIMIT 1;
        """
        rs = tx.execute(
            session.prepare(select_q),
            {"$salary_id": salary_id, "$firm_id": firm_id, "$user_id": user_id},
        )
        if not rs or not rs[0].rows:
            tx.rollback()
            return {"status": "NOT_FOUND"}

        delete_q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $deleted_at AS Timestamp;
            DECLARE $updated_at AS Timestamp;
            UPDATE employee_salary
            SET status = "deleted", deleted_at = $deleted_at, updated_at = $updated_at
            WHERE salary_id = $salary_id AND firm_id = $firm_id AND user_id = $user_id;
        """
        tx.execute(
            session.prepare(delete_q),
            {
                "$salary_id": salary_id,
                "$firm_id": firm_id,
                "$user_id": user_id,
                "$deleted_at": now_utc(),
                "$updated_at": now_utc(),
            },
        )
        tx.commit()
        return {"status": "DELETED"}

    try:
        result = notices_pool.retry_operation_sync(_tx)
    except Exception as e:
        logger.error(
            "payroll_manager.salary_delete.tx_error",
            error=str(e),
            trace=traceback.format_exc(),
        )
        hlog.exception("payroll_manager.salary_delete.tx_error", error=str(e))
        return server_error("Internal Server Error")

    if result.get("status") == "NOT_FOUND":
        return not_found("Salary record not found")

    try:
        _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="your_salary_changed",
            data=_build_salary_change_notice_data(
                firm_id=firm_id,
                user_id=user_id,
                firm_name=_read_firm_name(
                    firms_pool=firms_pool,
                    firms_database=firms_database,
                    firm_id=firm_id,
                )
                or f"Фирма {firm_id}",
                salary_snapshot=_read_employee_salary_snapshot(
                    notices_pool=notices_pool,
                    notices_database=notices_database,
                    firm_id=firm_id,
                    user_id=user_id,
                ),
                effective_from=None,
                action_text="Запись зарплаты удалена",
                status_text="deleted",
            ),
        )
    except Exception as e:
        logger.error("payroll_manager.salary_upsert.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.salary_upsert.notice_failed", error=str(e))

    return ok(
        {
            "message": "Salary deleted",
            "firm_id": firm_id,
            "salary_id": salary_id,
            "user_id": user_id,
        }
    )


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
    salary_snapshot = (
        normalized_queue_item.get("employee_salary_snapshot")
        if isinstance(normalized_queue_item.get("employee_salary_snapshot"), list)
        else []
    )
    payment_breakdown = _build_accrual_payment_breakdown(
        total_amount_kopeks=amount_kopeks,
        salary_snapshot=salary_snapshot,
        event_at=event_at,
    )

    return {
        "firm_id": firm_id,
        "user_id": user_id,
        "user_name": user_name,
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


def handle_deferred_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    user_id = body.get("user_id")
    deferred_until_raw = body.get("deferred_until")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")

    deferred_until = _parse_iso_datetime(deferred_until_raw)
    if not deferred_until:
        return bad_request("deferred_until must be a valid ISO datetime")
    event_at = _server_now_iso()

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

    payload = {
        "firm_id": firm_id,
        "user_id": user_id,
        "deferred_until": deferred_until,
        "event_at": event_at,
    }

    try:
        event_id = create_event_entity(user_id, EVENT_DEFERRED, payload, logger, firm_id=firm_id, schema_version=3)
    except Exception as e:
        logger.error("payroll_manager.deferred.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.deferred.event_failed", error=str(e))
        return server_error("Event generation failed")
    try:
        worker_name = _read_user_full_name(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_id=user_id,
        ) or "Рабочий"
        _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="your_payout_deferred",
            data={
                "firm_id": firm_id,
                "firm_name": _read_firm_name(
                    firms_pool=firms_pool,
                    firms_database=firms_database,
                    firm_id=firm_id,
                )
                or f"Фирма {firm_id}",
                "user_id": user_id,
                "deferred_until": deferred_until,
            },
        )
        for supervisor_user_id in _read_supervisor_ids(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
        ):
            if supervisor_user_id == user_id:
                continue
            _send_notice_safe(
                logger=logger,
                hlog=hlog,
                user_id=supervisor_user_id,
                notice_type="worker_payout_deferred",
                data={
                    "firm_id": firm_id,
                    "user_id": user_id,
                    "worker_name": worker_name,
                    "deferred_until": deferred_until,
                },
            )
    except Exception as e:
        logger.error("payroll_manager.deferred.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.deferred.notice_failed", error=str(e))

    return created(
        {
            "message": "Deferred payout created",
            "event_id": event_id,
            "firm_id": firm_id,
            "user_id": user_id,
        }
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


def _parse_reward_linkage(body: dict) -> Tuple[Dict[str, Any], Optional[str]]:
    source_kind_raw = body.get("source_kind")
    source_appeal_id_raw = body.get("source_appeal_id")
    source_event_type_raw = body.get("source_event_type")
    source_event_id_raw = body.get("source_event_id")

    source_kind = None
    if source_kind_raw is not None:
        if not isinstance(source_kind_raw, str) or not source_kind_raw.strip():
            return {}, "source_kind must be a non-empty string"
        source_kind = source_kind_raw.strip().lower()
        if source_kind not in {"appeal_compensation"}:
            return {}, "source_kind must be 'appeal_compensation'"

    source_appeal_id = None
    if source_appeal_id_raw is not None:
        if not isinstance(source_appeal_id_raw, str) or not source_appeal_id_raw.strip():
            return {}, "source_appeal_id must be a non-empty string"
        source_appeal_id = source_appeal_id_raw.strip()
        if not is_uuid(source_appeal_id):
            return {}, "source_appeal_id must be a valid UUID"

    source_event_type = None
    if source_event_type_raw is not None:
        if not isinstance(source_event_type_raw, str) or not source_event_type_raw.strip():
            return {}, "source_event_type must be a non-empty string"
        source_event_type = source_event_type_raw.strip().lower()
        if source_event_type != "fine":
            return {}, "source_event_type must be 'fine'"

    source_event_id = None
    if source_event_id_raw is not None:
        if not isinstance(source_event_id_raw, str) or not source_event_id_raw.strip():
            return {}, "source_event_id must be a non-empty string"
        source_event_id = source_event_id_raw.strip()
        if not is_uuid(source_event_id):
            return {}, "source_event_id must be a valid UUID"

    has_source_fields = any(v is not None for v in [source_appeal_id, source_event_type, source_event_id])
    if has_source_fields and source_kind is None:
        return {}, "source_kind is required when source_* fields are provided"

    if source_kind == "appeal_compensation":
        if not source_appeal_id:
            return {}, "source_appeal_id is required for source_kind=appeal_compensation"
        if not source_event_id:
            return {}, "source_event_id is required for source_kind=appeal_compensation"
        source_event_type = source_event_type or "fine"
        if source_event_type != "fine":
            return {}, "source_event_type must be 'fine' for source_kind=appeal_compensation"

    payload: Dict[str, Any] = {}
    if source_kind is not None:
        payload["source_kind"] = source_kind
    if source_appeal_id is not None:
        payload["source_appeal_id"] = source_appeal_id
    if source_event_type is not None:
        payload["source_event_type"] = source_event_type
    if source_event_id is not None:
        payload["source_event_id"] = source_event_id
    return payload, None


def _handle_fine_reward(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
    event_type: str,
    success_message: str,
):
    user_id = body.get("user_id")
    object_id = body.get("object_id")
    theme = body.get("theme")
    amount_kopeks = body.get("amount_kopeks")
    message = body.get("message")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not isinstance(object_id, str) or not object_id.strip():
        return bad_request("object_id is required")
    if not is_uuid(object_id.strip()):
        return bad_request("object_id must be a valid UUID")
    if not isinstance(theme, str) or not theme.strip():
        return bad_request("theme is required")
    if not isinstance(amount_kopeks, int) or amount_kopeks < 0:
        return bad_request("amount_kopeks must be a non-negative integer")
    event_at = _server_now_iso()

    attachments_json = _parse_json_value(body.get("attachments_json"))
    if attachments_json is not None and not isinstance(attachments_json, list):
        return bad_request("attachments_json must be an array")

    try:
        if attachments_json is not None:
            attachments_json = _validate_field_type("attachments_json", attachments_json, logger)
    except ValueError as e:
        return bad_request(str(e))
    except Exception:
        logger.error("payroll_manager.metadata_validation_failed", trace=traceback.format_exc())
        return server_error("Metadata validation failed")

    if message is not None and not isinstance(message, str):
        return bad_request("message must be a string")

    user_id = user_id.strip()
    object_id = object_id.strip()

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

    payload = {
        "firm_id": firm_id,
        "user_id": user_id,
        "object_id": object_id,
        "theme": theme.strip(),
        "amount_kopeks": amount_kopeks,
        "message": message,
        "attachments_json": attachments_json,
        "event_at": event_at,
    }
    schema_version = 2
    if event_type == EVENT_REWARD:
        reward_linkage, linkage_error = _parse_reward_linkage(body)
        if linkage_error:
            return bad_request(linkage_error)
        payload.update(reward_linkage)
        schema_version = 3

    try:
        event_id = create_event_entity(user_id, event_type, payload, logger, firm_id=firm_id, schema_version=schema_version)
    except Exception as e:
        logger.error("payroll_manager.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.event_failed", error=str(e))
        return server_error("Event generation failed")
    try:
        if event_type == EVENT_FINE:
            _send_notice_safe(
                logger=logger,
                hlog=hlog,
                user_id=user_id,
                notice_type="you_received_fine",
                data={
                    "firm_id": firm_id,
                    "user_id": user_id,
                    "object_id": object_id,
                    "fine_id": event_id,
                    "amount_text": _format_money_kopeks(amount_kopeks),
                    "reason": theme.strip(),
                },
            )
        elif event_type == EVENT_REWARD:
            _send_notice_safe(
                logger=logger,
                hlog=hlog,
                user_id=user_id,
                notice_type="you_received_reward",
                data={
                    "firm_id": firm_id,
                    "user_id": user_id,
                    "object_id": object_id,
                    "reward_id": event_id,
                    "amount_text": _format_money_kopeks(amount_kopeks),
                    "comment": (message or "").strip() or theme.strip(),
                },
            )
    except Exception as e:
        logger.error("payroll_manager.fine_reward.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.fine_reward.notice_failed", error=str(e))

    return created(
        {
            "message": success_message,
            "event_id": event_id,
            "firm_id": firm_id,
            "user_id": user_id,
        }
    )


def handle_fine_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    return _handle_fine_reward(
        body=body,
        firm_id=firm_id,
        caller_user_id=caller_user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
        event_type=EVENT_FINE,
        success_message="Fine created",
    )


def handle_reward_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    return _handle_fine_reward(
        body=body,
        firm_id=firm_id,
        caller_user_id=caller_user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
        event_type=EVENT_REWARD,
        success_message="Reward created",
    )
