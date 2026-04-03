# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from utils import ok_response, bad_request
from common import safe_json
from constants import EVENT_TYPE_OBJ_ENTER, EVENT_TYPE_OBJ_LEAVE
from event_state import extract_user_id, fetch_firm_event_states
from handlers_employee_finance import _coerce_datetime_utc
from features.object_activity_presence import (
    handle_object_activity_presence as feature_handle_object_activity_presence,
)


SHIFT_PRESENCE_TERMINAL_STATUSES = {"completed", "force_completed", "cancelled", "force_cancelled", "rejected"}
DEAL_PRESENCE_TERMINAL_STATUSES = {"archived", "completed", "force_completed", "cancelled", "force_cancelled", "rejected"}
SHIFT_PRESENCE_TERMINAL_EVENT_BY_STATUS = {
    "completed": "shift_end",
    "force_completed": "shift_force_end",
    "cancelled": "shift_cancel",
    "force_cancelled": "shift_force_end",
    "rejected": "shift_refuse",
}
DEAL_PRESENCE_TERMINAL_EVENT_BY_STATUS = {
    "archived": "deal_complete",
    "completed": "deal_complete",
    "force_completed": "deal_force_end",
    "cancelled": "deal_cancel",
    "force_cancelled": "deal_force_end",
    "rejected": "deal_refuse",
}


def _norm_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_date_utc(date_str: str) -> Tuple[datetime, datetime]:
    dt = datetime.strptime(str(date_str or "").strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return dt, dt + timedelta(days=1)


def _normalize_ids_list(raw: Any) -> List[str]:
    parsed = safe_json(raw)
    if not isinstance(parsed, list):
        return []
    out: List[str] = []
    seen = set()
    for item in parsed:
        sid = _norm_str(item)
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def _fetch_object_employee_rows(*, firms_pool, firms_database, firm_id, object_id):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        SELECT user_id, object_ids, role_type, status
        FROM firm_employees
        WHERE firm_id = $firm_id;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            status = _norm_str(getattr(row, "status", None)).lower()
            if not status.startswith("active_"):
                continue
            object_ids = _normalize_ids_list(getattr(row, "object_ids", None))
            if object_id not in object_ids:
                continue
            user_id = _norm_str(getattr(row, "user_id", None))
            if not user_id:
                continue
            result.append(
                {
                    "user_id": user_id,
                    "role_type": _norm_str(getattr(row, "role_type", None)).lower(),
                    "status": status,
                }
            )

    firms_pool.retry_operation_sync(_tx)
    return result


def _fetch_object_shifts_for_day(*, objects_pool, objects_database, object_id, start_at, end_at):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $object_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT
          shift_id,
          object_id,
          shift_name,
          base_payment,
          deadline_at,
          start_at,
          opened_at,
          closed_at,
          status,
          created_at,
          updated_at
        FROM firm_shifts
        WHERE object_id = $object_id
          AND (
            (
              status IN ('pending', 'active')
              AND (start_at IS NULL OR start_at < $end_at)
            )
            OR
            (
              status IN ('cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND (
                (closed_at IS NOT NULL AND closed_at >= $start_at AND closed_at < $end_at)
                OR
                (closed_at IS NULL AND updated_at >= $start_at AND updated_at < $end_at)
              )
            )
          );
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$object_id": object_id, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            shift_id = _norm_str(getattr(row, "shift_id", None))
            if not shift_id:
                continue
            result.append(
                {
                    "shift_id": shift_id,
                    "object_id": _norm_str(getattr(row, "object_id", None)),
                    "shift_name": _norm_str(getattr(row, "shift_name", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "deadline_at": getattr(row, "deadline_at", None),
                    "start_at": getattr(row, "start_at", None),
                    "opened_at": getattr(row, "opened_at", None),
                    "closed_at": getattr(row, "closed_at", None),
                    "status": _norm_str(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return result


def _fetch_object_deals_for_day(*, objects_pool, objects_database, object_id, start_at, end_at):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $object_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT
          deal_id,
          object_id,
          deal_name,
          base_payment,
          deadline_at,
          start_at,
          status,
          created_at,
          updated_at
        FROM firm_deals
        WHERE object_id = $object_id
          AND (
            (
              status IN ('active')
              AND (start_at IS NULL OR start_at < $end_at)
            )
            OR
            (
              status IN ('archived', 'cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND updated_at >= $start_at AND updated_at < $end_at
            )
          );
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$object_id": object_id, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            deal_id = _norm_str(getattr(row, "deal_id", None))
            if not deal_id:
                continue
            result.append(
                {
                    "deal_id": deal_id,
                    "object_id": _norm_str(getattr(row, "object_id", None)),
                    "deal_name": _norm_str(getattr(row, "deal_name", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "deadline_at": getattr(row, "deadline_at", None),
                    "start_at": getattr(row, "start_at", None),
                    "status": _norm_str(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return result


def _fetch_assign_event_rows(*, events_pool, events_database, firm_id, end_at):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at, sequence_number
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type IN ('shift_assign', 'deal_assign')
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = _norm_str(getattr(row, "event_id", None))
            if not event_id:
                continue
            result.append(
                {
                    "event_id": event_id,
                    "event_type": _norm_str(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return result


def _build_latest_assign_maps(*, assign_event_rows, states_by_event_id, shift_ids, deal_ids):
    latest_shift_by_id: Dict[str, Dict[str, Any]] = {}
    latest_deal_by_id: Dict[str, Dict[str, Any]] = {}
    shift_set = {_norm_str(v) for v in shift_ids if _norm_str(v)}
    deal_set = {_norm_str(v) for v in deal_ids if _norm_str(v)}

    for row in assign_event_rows:
        event_id = _norm_str(row.get("event_id"))
        event_type = _norm_str(row.get("event_type")).lower()
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        sequence_number = int(row.get("sequence_number") or 0)
        event_at = _to_iso_utc(state.get("event_at")) or _to_iso_utc(row.get("created_at"))
        if event_type == "shift_assign":
            shift_id = _norm_str(state.get("shift_id"))
            if not shift_id or shift_id not in shift_set:
                continue
            current = latest_shift_by_id.get(shift_id)
            if current is None or sequence_number > int(current.get("sequence_number") or 0):
                latest_shift_by_id[shift_id] = {
                    "shift_id": shift_id,
                    "worker_id": _norm_str(state.get("worker_id")),
                    "object_id": _norm_str(state.get("object_id")),
                    "event_id": event_id,
                    "event_at": event_at,
                    "sequence_number": sequence_number,
                }
        elif event_type == "deal_assign":
            deal_id = _norm_str(state.get("deal_id"))
            if not deal_id or deal_id not in deal_set:
                continue
            current = latest_deal_by_id.get(deal_id)
            if current is None or sequence_number > int(current.get("sequence_number") or 0):
                latest_deal_by_id[deal_id] = {
                    "deal_id": deal_id,
                    "worker_id": _norm_str(state.get("worker_id")),
                    "object_id": _norm_str(state.get("object_id")),
                    "event_id": event_id,
                    "event_at": event_at,
                    "sequence_number": sequence_number,
                }

    return latest_shift_by_id, latest_deal_by_id


def _fetch_manual_presence_rows(*, events_pool, events_database, user_ids, start_at, end_at):
    ids = _norm_ids(user_ids)
    if not ids:
        return []
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $user_ids AS List<Utf8>;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT user_id, event_id, event_type, created_at, sequence_number
        FROM user_events
        WHERE user_id IN $user_ids
          AND event_type IN ('{EVENT_TYPE_OBJ_ENTER}', '{EVENT_TYPE_OBJ_LEAVE}')
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$user_ids": ids, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = _norm_str(getattr(row, "event_id", None))
            if not event_id:
                continue
            result.append(
                {
                    "user_id": _norm_str(getattr(row, "user_id", None)),
                    "event_id": event_id,
                    "event_type": _norm_str(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return result


def _build_latest_manual_presence_by_user(*, manual_presence_rows, states_by_event_id, firm_id, object_id):
    latest_by_user: Dict[str, Dict[str, Any]] = {}
    for row in manual_presence_rows:
        event_id = _norm_str(row.get("event_id"))
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        if _norm_str(state.get("firm_id")) not in ("", firm_id):
            continue
        if _norm_str(state.get("object_id")) != object_id:
            continue
        user_id = _norm_str(extract_user_id(state) or row.get("user_id"))
        if not user_id:
            continue
        sequence_number = int(row.get("sequence_number") or 0)
        current = latest_by_user.get(user_id)
        if current is not None and sequence_number <= int(current.get("sequence_number") or 0):
            continue
        latest_by_user[user_id] = {
            "event_id": event_id,
            "event_type": _norm_str(row.get("event_type")).lower(),
            "event_at": _to_iso_utc(state.get("event_at")) or _to_iso_utc(row.get("created_at")),
            "sequence_number": sequence_number,
        }
    return latest_by_user


def _candidate(event_type: str, event_at: Any, *, status: str, is_present: bool, event_id: Optional[str] = None):
    dt = _coerce_datetime_utc(event_at)
    if dt is None:
        return None
    return {
        "event_type": event_type,
        "event_at": dt,
        "status": status,
        "is_present": is_present,
        "event_id": event_id,
    }


def _pick_latest_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    priority = {"finished": 2, "present": 1, "absent": 0}
    return max(
        candidates,
        key=lambda item: (
            item.get("event_at") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            priority.get(_norm_str(item.get("status")).lower(), -1),
        ),
    )


def _role_label_from_role_type(role_type: str) -> Optional[str]:
    normalized = _norm_str(role_type).lower()
    if normalized == "worker":
        return "Рабочий"
    if normalized == "foreman":
        return "Бригадир"
    return None


def _resolve_object_presence_worker(
    *,
    user_id: str,
    role_type: str,
    shifts: List[Dict[str, Any]],
    deals: List[Dict[str, Any]],
    latest_manual_presence: Optional[Dict[str, Any]],
    evaluation_at: datetime,
    selected_date_is_today: bool,
    selected_date_is_future: bool,
):
    candidates: List[Dict[str, Any]] = []
    is_foreman = "foreman" in role_type

    if is_foreman:
        if isinstance(latest_manual_presence, dict):
            event_type = _norm_str(latest_manual_presence.get("event_type")).lower()
            if event_type == EVENT_TYPE_OBJ_ENTER:
                candidate = _candidate(
                    event_type,
                    latest_manual_presence.get("event_at"),
                    status="present",
                    is_present=True,
                    event_id=_norm_str(latest_manual_presence.get("event_id")) or None,
                )
                if candidate:
                    candidates.append(candidate)
            elif event_type == EVENT_TYPE_OBJ_LEAVE:
                candidate = _candidate(
                    event_type,
                    latest_manual_presence.get("event_at"),
                    status="finished",
                    is_present=False,
                    event_id=_norm_str(latest_manual_presence.get("event_id")) or None,
                )
                if candidate:
                    candidates.append(candidate)
        return _pick_latest_candidate(candidates)

    for shift in shifts:
        status = _norm_str(shift.get("status")).lower()
        opened_at = _coerce_datetime_utc(shift.get("opened_at"))
        deadline_at = _coerce_datetime_utc(shift.get("deadline_at"))
        closed_at = _coerce_datetime_utc(shift.get("closed_at"))
        updated_at = _coerce_datetime_utc(shift.get("updated_at"))
        created_at = _coerce_datetime_utc(shift.get("created_at"))
        assign_at = _coerce_datetime_utc(shift.get("assign_event_at"))

        if status in SHIFT_PRESENCE_TERMINAL_STATUSES:
            candidate = _candidate(
                SHIFT_PRESENCE_TERMINAL_EVENT_BY_STATUS.get(status, "shift_end"),
                closed_at or updated_at or created_at,
                status="finished",
                is_present=False,
                event_id=_norm_str(shift.get("terminal_event_id")) or None,
            )
            if candidate:
                candidates.append(candidate)
            continue

        if status == "active" and opened_at is not None:
            if selected_date_is_today and (deadline_at is None or evaluation_at <= deadline_at):
                candidate = _candidate(
                    "shift_start",
                    opened_at,
                    status="present",
                    is_present=True,
                    event_id=_norm_str(shift.get("start_event_id")) or None,
                )
                if candidate:
                    candidates.append(candidate)
            else:
                candidate = _candidate(
                    "shift_start",
                    opened_at,
                    status="absent",
                    is_present=False,
                    event_id=_norm_str(shift.get("start_event_id")) or None,
                )
                if candidate:
                    candidates.append(candidate)
            continue

        candidate = _candidate(
            "shift_assign",
            assign_at or _coerce_datetime_utc(shift.get("start_at")) or created_at,
            status="absent",
            is_present=False,
            event_id=_norm_str(shift.get("assign_event_id")) or None,
        )
        if candidate:
            candidates.append(candidate)

    for deal in deals:
        status = _norm_str(deal.get("status")).lower()
        deadline_at = _coerce_datetime_utc(deal.get("deadline_at"))
        start_at = _coerce_datetime_utc(deal.get("start_at"))
        updated_at = _coerce_datetime_utc(deal.get("updated_at"))
        created_at = _coerce_datetime_utc(deal.get("created_at"))
        assign_at = _coerce_datetime_utc(deal.get("assign_event_at"))

        if status in DEAL_PRESENCE_TERMINAL_STATUSES:
            candidate = _candidate(
                DEAL_PRESENCE_TERMINAL_EVENT_BY_STATUS.get(status, "deal_complete"),
                updated_at or created_at,
                status="finished",
                is_present=False,
                event_id=_norm_str(deal.get("terminal_event_id")) or None,
            )
            if candidate:
                candidates.append(candidate)
            continue

        deal_is_started = start_at is None or evaluation_at >= start_at
        deal_is_not_overdue = deadline_at is None or evaluation_at <= deadline_at
        if status == "active" and selected_date_is_today and deal_is_started and deal_is_not_overdue:
            candidate = _candidate(
                "deal_assign",
                start_at or assign_at or created_at,
                status="present",
                is_present=True,
                event_id=_norm_str(deal.get("assign_event_id")) or None,
            )
            if candidate:
                candidates.append(candidate)
            continue

        if status == "active":
            candidate = _candidate(
                "deal_assign",
                start_at or assign_at or created_at,
                status="absent",
                is_present=False,
                event_id=_norm_str(deal.get("assign_event_id")) or None,
            )
            if candidate:
                candidates.append(candidate)
            continue

        candidate = _candidate(
            "deal_assign",
            assign_at or start_at or created_at,
            status="absent",
            is_present=False,
            event_id=_norm_str(deal.get("assign_event_id")) or None,
        )
        if candidate:
            candidates.append(candidate)

    if isinstance(latest_manual_presence, dict):
        event_type = _norm_str(latest_manual_presence.get("event_type")).lower()
        if event_type == EVENT_TYPE_OBJ_LEAVE:
            candidate = _candidate(
                event_type,
                latest_manual_presence.get("event_at"),
                status="finished",
                is_present=False,
                event_id=_norm_str(latest_manual_presence.get("event_id")) or None,
            )
            if candidate:
                candidates.append(candidate)

    return _pick_latest_candidate(candidates)


def _norm_ids(values):
    ids = []
    for v in values or []:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            ids.append(s)
    # de-dup, keep order
    seen = set()
    out = []
    for x in ids:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _fetch_user_profiles_map(*, firms_pool, firms_database, user_ids):
    ids = _norm_ids(user_ids)
    if not ids:
        return {}

    result_map = {}

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $user_ids AS List<Utf8>;
        SELECT user_id, full_name, email, phone_number, tags_json
        FROM UserProfiles
        WHERE user_id IN $user_ids;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$user_ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for r in rows:
            uid = str(getattr(r, "user_id", "") or "").strip()
            if not uid:
                continue
            tags_val = safe_json(getattr(r, "tags_json", None))
            if not isinstance(tags_val, list):
                tags_val = []
            result_map[uid] = {
                "user_id": uid,
                "full_name": getattr(r, "full_name", None),
                "email": getattr(r, "email", None),
                "phone_number": getattr(r, "phone_number", None),
                "tags_json": tags_val,
            }

    firms_pool.retry_operation_sync(_tx)
    return result_map


def _fetch_object_names_map(*, objects_pool, objects_database, object_ids):
    ids = _norm_ids(object_ids)
    if not ids:
        return {}

    result_map = {}

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $object_ids AS List<Utf8>;
        SELECT object_id, object_name
        FROM firm_objects
        WHERE object_id IN $object_ids;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$object_ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for r in rows:
            oid = str(getattr(r, "object_id", "") or "").strip()
            if not oid:
                continue
            result_map[oid] = str(getattr(r, "object_name", "") or "").strip() or None

    objects_pool.retry_operation_sync(_tx)
    return result_map


def _fetch_shifts_map(*, objects_pool, objects_database, shift_ids):
    ids = _norm_ids(shift_ids)
    if not ids:
        return {}

    result_map = {}

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $shift_ids AS List<Utf8>;
        SELECT shift_id, object_id, shift_name, base_payment, tags_json, deadline_at, start_at, opened_at, closed_at, status, created_at, updated_at
        FROM firm_shifts
        WHERE shift_id IN $shift_ids;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$shift_ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for r in rows:
            sid = str(getattr(r, "shift_id", "") or "").strip()
            if not sid:
                continue
            tags_val = safe_json(getattr(r, "tags_json", None))
            if not isinstance(tags_val, list):
                tags_val = []
            result_map[sid] = {
                "shift_id": sid,
                "object_id": getattr(r, "object_id", None),
                "shift_name": getattr(r, "shift_name", None),
                "base_payment": getattr(r, "base_payment", None),
                "tags_json": tags_val,
                "deadline_at": _to_iso_utc(getattr(r, "deadline_at", None)),
                "start_at": _to_iso_utc(getattr(r, "start_at", None)),
                "opened_at": _to_iso_utc(getattr(r, "opened_at", None)),
                "closed_at": _to_iso_utc(getattr(r, "closed_at", None)),
                "status": getattr(r, "status", None),
                "created_at": _to_iso_utc(getattr(r, "created_at", None)),
                "updated_at": _to_iso_utc(getattr(r, "updated_at", None)),
            }

    objects_pool.retry_operation_sync(_tx)
    return result_map


def _fetch_deals_map(*, objects_pool, objects_database, deal_ids):
    ids = _norm_ids(deal_ids)
    if not ids:
        return {}

    result_map = {}

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $deal_ids AS List<Utf8>;
        SELECT deal_id, object_id, deal_name, base_payment, norm_quantity, price_per_unit, deadline_at, start_at, status, created_at, updated_at
        FROM firm_deals
        WHERE deal_id IN $deal_ids;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$deal_ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for r in rows:
            did = str(getattr(r, "deal_id", "") or "").strip()
            if not did:
                continue
            result_map[did] = {
                "deal_id": did,
                "object_id": getattr(r, "object_id", None),
                "deal_name": getattr(r, "deal_name", None),
                "base_payment": getattr(r, "base_payment", None),
                "norm_quantity": getattr(r, "norm_quantity", None),
                "price_per_unit": getattr(r, "price_per_unit", None),
                "deadline_at": _to_iso_utc(getattr(r, "deadline_at", None)),
                "start_at": _to_iso_utc(getattr(r, "start_at", None)),
                "status": getattr(r, "status", None),
                "created_at": _to_iso_utc(getattr(r, "created_at", None)),
                "updated_at": _to_iso_utc(getattr(r, "updated_at", None)),
            }

    objects_pool.retry_operation_sync(_tx)
    return result_map


def _to_iso_utc(value):
    if value is None:
        return None

    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        ts = float(value)
        abs_ts = abs(ts)
        if abs_ts >= 1_000_000_000_000_000_000:  # ns
            dt = datetime.fromtimestamp(ts / 1_000_000_000, tz=timezone.utc)
        elif abs_ts >= 1_000_000_000_000_000:  # us
            dt = datetime.fromtimestamp(ts / 1_000_000, tz=timezone.utc)
        elif abs_ts >= 1_000_000_000_000:  # ms
            dt = datetime.fromtimestamp(ts / 1_000, tz=timezone.utc)
        else:  # s
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            return _to_iso_utc(int(raw))
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _presence_status_by_event_type(event_type):
    normalized = str(event_type or "").strip().lower()
    if normalized == EVENT_TYPE_OBJ_ENTER:
        return "present"
    if normalized == EVENT_TYPE_OBJ_LEAVE:
        return "left"
    return None


def _extract_profile_role_label(profile):
    if not isinstance(profile, dict):
        return None
    tags = profile.get("tags_json")
    if not isinstance(tags, list):
        return None
    for raw in tags:
        if isinstance(raw, str):
            s = raw.strip()
            if s:
                return s
            continue
        if isinstance(raw, dict):
            for key in ("label", "name", "title", "role"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _fetch_worker_percents_map(*, firms_pool, firms_database, firm_id):
    query_attributions = f"""
    SELECT worker_user_id, percent_snapshot
    FROM dispatcher_attributions
    WHERE firm_id = '{firm_id}'
    ORDER BY
        CASE
            WHEN attribution_type = 'dispatcher' THEN 0
            WHEN attribution_type = 'nominal' THEN 1
            ELSE 2
        END ASC,
        updated_at DESC,
        created_at DESC;
    """

    attributions_result = None

    def _read_attributions(session):
        nonlocal attributions_result
        attributions_result = session.transaction().execute(query_attributions, commit_tx=True)

    firms_pool.retry_operation_sync(_read_attributions)

    worker_percents = {}
    if attributions_result and attributions_result[0].rows:
        for row in attributions_result[0].rows:
            worker_id = str(row.worker_user_id)
            if worker_id in worker_percents:
                continue
            worker_percents[worker_id] = row.percent_snapshot
    return worker_percents


def handle_object_finance_history(body, firm_id, objects_pool, objects_database, events_pool, events_database, firms_pool, firms_database, meta_pool, meta_database, logger, hlog):
    logger.info("analytics_getter.object_finance_history.start", firm_id=firm_id)
    
    object_id = body.get("object_id")
    if not object_id:
        logger.warn("analytics_getter.object_finance_history.missing_object_id")
        return bad_request("object_id is required")
    
    month = body.get("month")
    year = body.get("year")
    if not month or not year:
        logger.warn("analytics_getter.object_finance_history.missing_date")
        return bad_request("month and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.object_finance_history.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    logger.info("analytics_getter.object_finance_history.query_object", object_id=object_id)
    
    try:
        query_object = f"""
        SELECT object_id, object_name, attachments_json, extra_charges_json, contact_person_json
        FROM firm_objects
        WHERE object_id = '{object_id}' AND firm_id = '{firm_id}';
        """
        
        object_result = None
        def _read_object(session):
            nonlocal object_result
            object_result = session.transaction().execute(query_object, commit_tx=True)
        
        objects_pool.retry_operation_sync(_read_object)
        
        obj_rows = list(object_result[0].rows) if object_result and object_result[0].rows else []
        if not obj_rows:
            logger.warn("analytics_getter.object_finance_history.object_not_found", object_id=object_id)
            return bad_request("Object not found")
        
        obj_data = obj_rows[0]
        
        query_finance_events = f"""
        SELECT event_id, event_type, created_at
        FROM finance_events
        WHERE firm_id = '{firm_id}'
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        finance_result = None
        def _read_finance(session):
            nonlocal finance_result
            finance_result = session.transaction().execute(query_finance_events, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_finance)
        
        finance_events = []
        if finance_result and finance_result[0].rows:
            for row in finance_result[0].rows:
                finance_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                })

        event_ids = [str(e.get("event_id") or "").strip() for e in finance_events]
        event_ids = [eid for eid in event_ids if eid]
        event_states = {}
        if event_ids:
            event_states = fetch_firm_event_states(
                meta_pool=meta_pool,
                meta_database=meta_database,
                firm_id=firm_id,
                event_ids=event_ids,
                logger=logger,
            )
            for ev in finance_events:
                eid = str(ev.get("event_id") or "").strip()
                if eid:
                    ev["state"] = event_states.get(eid)

        # Filter: keep only events whose state.object_id matches the requested object_id
        filtered = []
        for ev in finance_events:
            st = ev.get("state")
            if not isinstance(st, dict):
                continue
            ev_obj_id = str(st.get("object_id") or "").strip()
            if ev_obj_id == object_id:
                filtered.append(ev)
        logger.info(
            "analytics_getter.object_finance_history.filter_by_object",
            object_id=object_id,
            total_events=len(finance_events),
            filtered_events=len(filtered),
        )
        finance_events = filtered

        # Enrich: user profiles + firm_shifts/firm_deals records (batch)
        user_id_keys = ["user_id", "worker_id", "assigned_by", "canceled_by", "completed_by"]
        all_user_ids = []
        all_shift_ids = []
        all_deal_ids = []
        for ev in finance_events:
            st = ev.get("state")
            if not isinstance(st, dict):
                continue
            for k in user_id_keys:
                v = st.get(k)
                if v:
                    all_user_ids.append(v)
            if st.get("shift_id"):
                all_shift_ids.append(st.get("shift_id"))
            if st.get("deal_id"):
                all_deal_ids.append(st.get("deal_id"))

        profiles_by_id = _fetch_user_profiles_map(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=all_user_ids,
        )
        shifts_by_id = _fetch_shifts_map(
            objects_pool=objects_pool,
            objects_database=objects_database,
            shift_ids=all_shift_ids,
        )
        deals_by_id = _fetch_deals_map(
            objects_pool=objects_pool,
            objects_database=objects_database,
            deal_ids=all_deal_ids,
        )

        for ev in finance_events:
            st = ev.get("state")
            if not isinstance(st, dict):
                continue

            # user profiles (if corresponding id key is present)
            for k in user_id_keys:
                uid = st.get(k)
                if not uid:
                    continue
                uid = str(uid).strip()
                if not uid:
                    continue
                prof = profiles_by_id.get(uid)
                if prof:
                    st[f"{k}_profile"] = prof
                    if k == "user_id":
                        st["user_profile"] = prof

            # shift record
            shift_id = st.get("shift_id")
            if shift_id:
                sid = str(shift_id).strip()
                rec = shifts_by_id.get(sid)
                if rec:
                    st["shift"] = rec
                    # flatten most-used fields for UI compatibility
                    st.setdefault("shift_name", rec.get("shift_name"))
                    st.setdefault("base_payment", rec.get("base_payment"))
                    st.setdefault("deadline_at", rec.get("deadline_at"))
                    st.setdefault("start_at", rec.get("start_at"))
                    st.setdefault("end_at", rec.get("closed_at"))

            # deal record
            deal_id = st.get("deal_id")
            if deal_id:
                did = str(deal_id).strip()
                rec = deals_by_id.get(did)
                if rec:
                    st["deal"] = rec
                    st.setdefault("deal_name", rec.get("deal_name"))
                    st.setdefault("base_payment", rec.get("base_payment"))
                    st.setdefault("deadline_at", rec.get("deadline_at"))
                    st.setdefault("start_at", rec.get("start_at"))
                    st.setdefault("norm_quantity", rec.get("norm_quantity"))
                    st.setdefault("price_per_unit", rec.get("price_per_unit"))

        query_employees = f"""
        SELECT user_id, object_ids
        FROM firm_employees
        WHERE firm_id = '{firm_id}';
        """
        
        employees_result = None
        def _read_employees(session):
            nonlocal employees_result
            employees_result = session.transaction().execute(query_employees, commit_tx=True)
        
        firms_pool.retry_operation_sync(_read_employees)
        
        workers_on_object = []
        if employees_result and employees_result[0].rows:
            for row in employees_result[0].rows:
                import json
                obj_ids = json.loads(row.object_ids) if row.object_ids else []
                if object_id in obj_ids:
                    workers_on_object.append(row.user_id)
        
        worker_percents = _fetch_worker_percents_map(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
        )
        
        workers_summary = []
        for worker_id in workers_on_object:
            workers_summary.append({
                "user_id": worker_id,
                "dispatcher_percent": worker_percents.get(worker_id, 0.0),
            })
        
        logger.info("analytics_getter.object_finance_history.success", object_id=object_id, events_count=len(finance_events))
        
        return ok_response({
            "object": {
                "object_id": obj_data.object_id,
                "object_name": obj_data.object_name,
                "extra_charges_json": obj_data.extra_charges_json,
                "contact_person_json": obj_data.contact_person_json,
                "attachments_json": obj_data.attachments_json,
            },
            "finance_events": finance_events,
            "workers_summary": workers_summary,
        })
        
    except Exception as e:
        logger.error("analytics_getter.object_finance_history.error", error=str(e))
        hlog.exception("analytics_getter.object_finance_history.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_object_activity_presence(
    body,
    firm_id,
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
    return feature_handle_object_activity_presence(
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


def handle_my_object_presence(
    *,
    body,
    firm_id,
    caller_user_id,
    objects_pool,
    objects_database,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info(
        "analytics_getter.my_object_presence.start",
        firm_id=firm_id,
        caller_user_id=caller_user_id,
    )

    if not str(caller_user_id or "").strip():
        logger.warn("analytics_getter.my_object_presence.missing_user_id")
        return bad_request("caller user_id is required")

    try:
        query_user_events = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $user_id AS Utf8;
        SELECT event_id, event_type, created_at
        FROM user_events
        WHERE user_id = $user_id
          AND event_type IN ('{EVENT_TYPE_OBJ_ENTER}', '{EVENT_TYPE_OBJ_LEAVE}')
        ORDER BY sequence_number DESC
        LIMIT 1;
        """

        events_result = None

        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(
                session.prepare(query_user_events),
                {"$user_id": caller_user_id},
                commit_tx=True,
            )

        events_pool.retry_operation_sync(_read_events)

        rows = list(events_result[0].rows) if events_result and events_result[0].rows else []
        if not rows:
            logger.info(
                "analytics_getter.my_object_presence.empty",
                firm_id=firm_id,
                caller_user_id=caller_user_id,
            )
            return ok_response({
                "user_id": caller_user_id,
                "is_present": False,
                "status": "unknown",
                "object_id": None,
                "object_name": None,
                "last_event_type": None,
                "last_event_id": None,
                "last_event_at": None,
                "updated_at": _to_iso_utc(datetime.now(timezone.utc)),
            })

        row = rows[0]
        event_id = str(getattr(row, "event_id", "") or "").strip()
        event_type = str(getattr(row, "event_type", "") or "").strip()
        created_at = _to_iso_utc(getattr(row, "created_at", None))
        status = _presence_status_by_event_type(event_type) or "unknown"

        event_states = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=[event_id] if event_id else [],
            logger=logger,
        )
        state = event_states.get(event_id) if event_id else None
        if not isinstance(state, dict):
            state = {}

        object_id = str(state.get("object_id") or "").strip() or None
        object_names = _fetch_object_names_map(
            objects_pool=objects_pool,
            objects_database=objects_database,
            object_ids=[object_id] if object_id else [],
        )
        object_name = object_names.get(object_id) if object_id else None
        last_event_at = _to_iso_utc(state.get("event_at")) or created_at
        is_present = status == "present"

        logger.info(
            "analytics_getter.my_object_presence.success",
            firm_id=firm_id,
            caller_user_id=caller_user_id,
            is_present=is_present,
            object_id=object_id,
            last_event_type=event_type,
        )

        return ok_response({
            "user_id": caller_user_id,
            "is_present": is_present,
            "status": status,
            "object_id": object_id,
            "object_name": object_name,
            "last_event_type": event_type or None,
            "last_event_id": event_id or None,
            "last_event_at": last_event_at,
            "updated_at": _to_iso_utc(datetime.now(timezone.utc)),
        })
    except Exception as e:
        logger.error("analytics_getter.my_object_presence.error", error=str(e))
        hlog.exception("analytics_getter.my_object_presence.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_object_activity_timeline(
    body,
    firm_id,
    events_pool,
    events_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.object_activity_timeline.start", firm_id=firm_id)

    object_id = str(body.get("object_id") or "").strip()
    if not object_id:
        logger.warn("analytics_getter.object_activity_timeline.missing_object_id")
        return bad_request("object_id is required")

    date_str = body.get("date")
    if not date_str:
        logger.warn("analytics_getter.object_activity_timeline.missing_date")
        return bad_request("date is required (YYYY-MM-DD)")

    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        next_date = target_date + timedelta(days=1)
    except ValueError as e:
        logger.warn("analytics_getter.object_activity_timeline.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")

    try:
        query_object_events = f"""
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND created_at >= CAST('{target_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{next_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """

        events_result = None

        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_object_events, commit_tx=True)

        events_pool.retry_operation_sync(_read_events)

        raw_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                raw_events.append({
                    "event_id": str(getattr(row, "event_id", "") or "").strip(),
                    "event_type": str(getattr(row, "event_type", "") or "").strip(),
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                })

        event_ids = [e["event_id"] for e in raw_events if e.get("event_id")]
        event_states = {}
        if event_ids:
            event_states = fetch_firm_event_states(
                meta_pool=meta_pool,
                meta_database=meta_database,
                firm_id=firm_id,
                event_ids=event_ids,
                logger=logger,
            )

        worker_percents = _fetch_worker_percents_map(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
        )

        user_id_keys = ("user_id", "worker_id", "assigned_by", "canceled_by", "completed_by")
        user_ids = []
        for event in raw_events:
            state = event_states.get(event.get("event_id"))
            if not isinstance(state, dict):
                continue
            if str(state.get("object_id") or "").strip() != object_id:
                continue
            primary_user_id = extract_user_id(state)
            if primary_user_id:
                user_ids.append(primary_user_id)
            for key in user_id_keys:
                value = state.get(key)
                if value:
                    user_ids.append(value)

        profiles_by_id = _fetch_user_profiles_map(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=user_ids,
        )

        timeline_events = []
        workers_latest = {}
        for event in raw_events:
            event_id = event.get("event_id")
            if not event_id:
                continue

            state = event_states.get(event_id)
            if not isinstance(state, dict):
                continue

            state_object_id = str(state.get("object_id") or "").strip()
            if state_object_id != object_id:
                continue

            enriched_state = dict(state)
            for key in user_id_keys:
                value = enriched_state.get(key)
                if not value:
                    continue
                uid = str(value).strip()
                if not uid:
                    continue
                profile = profiles_by_id.get(uid)
                if profile:
                    enriched_state[f"{key}_profile"] = profile
                    if key == "user_id":
                        enriched_state["user_profile"] = profile

            primary_user_id = extract_user_id(enriched_state)
            if primary_user_id:
                profile = profiles_by_id.get(primary_user_id)
                if profile and "user_profile" not in enriched_state:
                    enriched_state["user_profile"] = profile
                if primary_user_id in worker_percents:
                    enriched_state["dispatcher_percent"] = worker_percents.get(primary_user_id)

            status = _presence_status_by_event_type(event.get("event_type"))
            event_at = _to_iso_utc(enriched_state.get("event_at")) or event.get("created_at")
            timeline_events.append({
                "event_id": event_id,
                "event_type": event.get("event_type"),
                "created_at": event.get("created_at"),
                "event_at": event_at,
                "user_id": primary_user_id,
                "status": status,
                "state": enriched_state,
            })

            if primary_user_id:
                workers_latest[primary_user_id] = {
                    "last_event_type": event.get("event_type"),
                    "last_event_at": event_at,
                    "is_present": status == "present",
                }

        workers_summary = []
        for user_id, meta in workers_latest.items():
            profile = profiles_by_id.get(user_id)
            workers_summary.append({
                "user_id": user_id,
                "user_profile": profile,
                "role_label": _extract_profile_role_label(profile),
                "dispatcher_percent": worker_percents.get(user_id),
                "last_event_type": meta.get("last_event_type"),
                "last_event_at": meta.get("last_event_at"),
                "is_present": bool(meta.get("is_present")),
            })

        workers_summary.sort(
            key=lambda item: (
                str(((item.get("user_profile") or {}).get("full_name") or "")).lower(),
                str(item.get("user_id") or ""),
            )
        )

        logger.info(
            "analytics_getter.object_activity_timeline.success",
            object_id=object_id,
            source_events=len(raw_events),
            events_count=len(timeline_events),
            workers_count=len(workers_summary),
        )

        return ok_response({
            "object_id": object_id,
            "date": date_str,
            "timeline_events": timeline_events,
            "worker_percents": worker_percents,
            "workers_summary": workers_summary,
        })

    except Exception as e:
        logger.error("analytics_getter.object_activity_timeline.error", error=str(e))
        hlog.exception("analytics_getter.object_activity_timeline.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")
