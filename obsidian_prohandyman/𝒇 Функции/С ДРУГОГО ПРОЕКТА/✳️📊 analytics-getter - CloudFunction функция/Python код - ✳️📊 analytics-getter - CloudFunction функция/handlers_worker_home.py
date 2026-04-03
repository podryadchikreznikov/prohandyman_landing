# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import ydb

from utils import bad_request, forbidden, ok_response
from utils.util_metadata import parse_json_value

from constants import EVENT_TYPE_FINE, EVENT_TYPE_ABSENCE
from event_state import extract_amount_kopeks, extract_user_id, fetch_firm_event_states

ACTIVE_WORKER_STATUSES = {"active_unattached", "active_attached"}


def _month_range(*, year: int, month: int) -> Tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _year_range(*, year: int) -> Tuple[datetime, datetime]:
    return datetime(year, 1, 1, tzinfo=timezone.utc), datetime(year + 1, 1, 1, tzinfo=timezone.utc)


def _day_range(*, date_value: str) -> Tuple[datetime, datetime]:
    start = datetime.strptime(date_value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _norm_text(value: Any) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except Exception:
            value = str(value)
    if value is None:
        return ""
    return str(value).strip()


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


def _chunked(values: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        return [values]
    return [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]


def _read_event_ids(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    table_name: str,
    event_types: List[str],
    start: datetime,
    end: datetime,
) -> List[str]:
    ids: List[str] = []

    def _tx(session: ydb.Session):
        types_yql = ", ".join([f"'{t}'" for t in event_types])
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT event_id
        FROM {table_name}
        WHERE firm_id = $firm_id
          AND event_type IN ({types_yql})
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
            eid = str(getattr(row, "event_id", "") or "").strip()
            if eid:
                ids.append(eid)

    events_pool.retry_operation_sync(_tx)
    return ids


def _read_worker_memberships_all_firms(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    user_id: str,
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen_firms: set[str] = set()

    def _read_firm_name(*, firm_id: str) -> str:
        def _tx_name(session: ydb.Session) -> str:
            q = f"""
            PRAGMA TablePathPrefix('{firms_database}');
            DECLARE $firm_id AS Utf8;
            SELECT firm_name
            FROM Firms
            WHERE firm_id = $firm_id
            LIMIT 1;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id},
                commit_tx=True,
            )
            if rs and rs[0].rows:
                return _norm_text(getattr(rs[0].rows[0], "firm_name", None))
            return ""

        return firms_pool.retry_operation_sync(_tx_name)

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $user_id AS Utf8;
        SELECT firm_id, role_type, status
        FROM firm_employees
        WHERE user_id = $user_id;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$user_id": user_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            firm_id = _norm_text(getattr(row, "firm_id", None))
            if not firm_id:
                continue
            if firm_id in seen_firms:
                continue
            status = _norm_text(getattr(row, "status", None)).lower()
            role_type = _norm_text(getattr(row, "role_type", None)).lower()
            if role_type != "worker":
                continue
            if status not in ACTIVE_WORKER_STATUSES:
                continue
            seen_firms.add(firm_id)
            out.append(
                {
                    "firm_id": firm_id,
                    "firm_name": _read_firm_name(firm_id=firm_id),
                    "role_type": role_type,
                    "employee_status": status,
                }
            )

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_worker_shifts_for_period(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    start: datetime,
    end: datetime,
    period_kind: str = "month",
) -> List[Dict[str, Any]]:
    def _tx(session: ydb.Session):
        active_time_condition = (
            """
              (
                (s.start_at IS NOT NULL AND s.start_at >= $start_at AND s.start_at < $end_at)
                OR
                (s.start_at IS NULL AND s.created_at >= $start_at AND s.created_at < $end_at)
              )
            """
            if period_kind == "day"
            else "(s.start_at IS NULL OR s.start_at < $end_at)"
        )
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT
          s.shift_id AS shift_id,
          s.object_id AS object_id,
          s.shift_name AS shift_name,
          s.base_payment AS base_payment,
          s.tags_json AS tags_json,
          s.deadline_at AS deadline_at,
          s.start_at AS start_at,
          s.opened_at AS opened_at,
          s.closed_at AS closed_at,
          s.status AS status,
          s.created_at AS created_at,
          s.updated_at AS updated_at,
          o.object_name AS object_name,
          o.address_json AS address_json,
          o.status AS object_status
        FROM firm_shifts AS s
        INNER JOIN firm_objects AS o ON o.object_id = s.object_id
        WHERE o.firm_id = $firm_id
          AND (
            (
              s.status IN ('pending', 'active')
              AND {active_time_condition}
            )
            OR
            (
              s.status IN ('cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND (
                (s.closed_at IS NOT NULL AND s.closed_at >= $start_at AND s.closed_at < $end_at)
                OR
                (s.closed_at IS NULL AND s.updated_at >= $start_at AND s.updated_at < $end_at)
              )
            )
          );
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": start, "$end_at": end},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        out: List[Dict[str, Any]] = []
        for r in rows:
            tags = parse_json_value(getattr(r, "tags_json", None))
            address = parse_json_value(getattr(r, "address_json", None))
            out.append(
                {
                    "shift_id": _norm_text(getattr(r, "shift_id", None)),
                    "object_id": _norm_text(getattr(r, "object_id", None)),
                    "shift_name": getattr(r, "shift_name", None),
                    "base_payment": getattr(r, "base_payment", None),
                    "tags_json": tags if isinstance(tags, list) else [],
                    "deadline_at": _to_iso_utc(getattr(r, "deadline_at", None)),
                    "start_at": _to_iso_utc(getattr(r, "start_at", None)),
                    "opened_at": _to_iso_utc(getattr(r, "opened_at", None)),
                    "closed_at": _to_iso_utc(getattr(r, "closed_at", None)),
                    "status": _norm_text(getattr(r, "status", None)),
                    "created_at": _to_iso_utc(getattr(r, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(r, "updated_at", None)),
                    "object_name": getattr(r, "object_name", None),
                    "address_json": address if isinstance(address, dict) else address,
                    "object_status": _norm_text(getattr(r, "object_status", None)),
                }
            )
        return out

    return objects_pool.retry_operation_sync(_tx)


def _read_worker_deals_for_period(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    start: datetime,
    end: datetime,
    period_kind: str = "month",
) -> List[Dict[str, Any]]:
    def _tx(session: ydb.Session):
        active_time_condition = (
            """
              (
                (d.start_at IS NOT NULL AND d.start_at >= $start_at AND d.start_at < $end_at)
                OR
                (d.start_at IS NULL AND d.created_at >= $start_at AND d.created_at < $end_at)
              )
            """
            if period_kind == "day"
            else "(d.start_at IS NULL OR d.start_at < $end_at)"
        )
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT
          d.deal_id AS deal_id,
          d.object_id AS object_id,
          d.deal_name AS deal_name,
          d.base_payment AS base_payment,
          d.norm_quantity AS norm_quantity,
          d.price_per_unit AS price_per_unit,
          d.deadline_at AS deadline_at,
          d.start_at AS start_at,
          d.status AS status,
          d.created_at AS created_at,
          d.updated_at AS updated_at,
          o.object_name AS object_name,
          o.address_json AS address_json,
          o.status AS object_status
        FROM firm_deals AS d
        INNER JOIN firm_objects AS o ON o.object_id = d.object_id
        WHERE o.firm_id = $firm_id
          AND (
            (
              d.status IN ('active')
              AND {active_time_condition}
            )
            OR
            (
              d.status IN ('archived', 'cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND d.updated_at >= $start_at
              AND d.updated_at < $end_at
            )
          );
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": start, "$end_at": end},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        out: List[Dict[str, Any]] = []
        for r in rows:
            address = parse_json_value(getattr(r, "address_json", None))
            out.append(
                {
                    "deal_id": _norm_text(getattr(r, "deal_id", None)),
                    "object_id": _norm_text(getattr(r, "object_id", None)),
                    "deal_name": getattr(r, "deal_name", None),
                    "base_payment": getattr(r, "base_payment", None),
                    "norm_quantity": getattr(r, "norm_quantity", None),
                    "price_per_unit": getattr(r, "price_per_unit", None),
                    "deadline_at": _to_iso_utc(getattr(r, "deadline_at", None)),
                    "start_at": _to_iso_utc(getattr(r, "start_at", None)),
                    "status": _norm_text(getattr(r, "status", None)),
                    "created_at": _to_iso_utc(getattr(r, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(r, "updated_at", None)),
                    "object_name": getattr(r, "object_name", None),
                    "address_json": address if isinstance(address, dict) else address,
                    "object_status": _norm_text(getattr(r, "object_status", None)),
                }
            )
        return out

    return objects_pool.retry_operation_sync(_tx)


def _resolve_latest_assign_states_for_items(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    firm_id: str,
    end: datetime,
    shift_ids: List[str],
    deal_ids: List[str],
    logger,
) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    shift_set: Set[str] = {_norm_text(x) for x in shift_ids if _norm_text(x)}
    deal_set: Set[str] = {_norm_text(x) for x in deal_ids if _norm_text(x)}
    if not shift_set and not deal_set:
        return {}, {}

    latest_shift: Dict[str, dict] = {}
    latest_deal: Dict[str, dict] = {}

    start_from_epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    bounded_lookback_start = end - timedelta(days=400)
    extended_lookback_start = end - timedelta(days=1600)
    candidate_starts = [
        bounded_lookback_start if bounded_lookback_start > start_from_epoch else start_from_epoch,
        extended_lookback_start if extended_lookback_start > start_from_epoch else start_from_epoch,
    ]

    # Deduplicate while preserving order.
    normalized_candidate_starts: List[datetime] = []
    seen: Set[str] = set()
    for candidate in candidate_starts:
        marker = candidate.isoformat()
        if marker in seen:
            continue
        seen.add(marker)
        normalized_candidate_starts.append(candidate)

    for window_idx, candidate_start in enumerate(normalized_candidate_starts):
        try:
            event_ids = _read_event_ids(
                events_pool=events_pool,
                events_database=events_database,
                firm_id=firm_id,
                table_name="object_events",
                event_types=["shift_assign", "deal_assign"],
                start=candidate_start,
                end=end,
            )
        except Exception as e:
            logger.warn(
                "analytics_getter.worker.assign_states.read_event_ids_failed",
                firm_id=firm_id,
                candidate_start=_to_iso_utc(candidate_start),
                candidate_end=_to_iso_utc(end),
                window_idx=window_idx,
                error=str(e),
            )
            continue

        if not event_ids:
            continue

        try:
            states = fetch_firm_event_states(
                meta_pool=meta_pool,
                meta_database=meta_database,
                firm_id=firm_id,
                event_ids=event_ids,
                logger=logger,
            )
        except Exception as e:
            logger.warn(
                "analytics_getter.worker.assign_states.fetch_states_failed",
                firm_id=firm_id,
                candidate_start=_to_iso_utc(candidate_start),
                candidate_end=_to_iso_utc(end),
                window_idx=window_idx,
                events_count=len(event_ids),
                error=str(e),
            )
            continue

        if not states:
            continue

        for event_id in event_ids:
            st = states.get(event_id)
            if not isinstance(st, dict):
                continue
            sid = _norm_text(st.get("shift_id"))
            if sid and sid in shift_set:
                latest_shift[sid] = st
            did = _norm_text(st.get("deal_id"))
            if did and did in deal_set:
                latest_deal[did] = st

        # Found latest states for all target items - no need to widen the window.
        if len(latest_shift) >= len(shift_set) and len(latest_deal) >= len(deal_set):
            break

    return latest_shift, latest_deal


def _collect_worker_assignments_for_firm(
    *,
    user_id: str,
    firm_id: str,
    firm_name: str,
    start: datetime,
    end: datetime,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    period_kind: str = "month",
    logger,
) -> Tuple[List[dict], List[dict]]:
    shifts_rows = _read_worker_shifts_for_period(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        start=start,
        end=end,
        period_kind=period_kind,
    )
    deals_rows = _read_worker_deals_for_period(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        start=start,
        end=end,
        period_kind=period_kind,
    )

    shift_ids = [x.get("shift_id") for x in shifts_rows if isinstance(x, dict) and x.get("shift_id")]
    deal_ids = [x.get("deal_id") for x in deals_rows if isinstance(x, dict) and x.get("deal_id")]

    latest_shift_state, latest_deal_state = _resolve_latest_assign_states_for_items(
        events_pool=events_pool,
        events_database=events_database,
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        end=end,
        shift_ids=shift_ids,
        deal_ids=deal_ids,
        logger=logger,
    )

    shifts: List[dict] = []
    for row in shifts_rows:
        shift_id = _norm_text(row.get("shift_id"))
        if not shift_id:
            continue
        assign_state = latest_shift_state.get(shift_id)
        if not isinstance(assign_state, dict):
            continue
        worker_id = extract_user_id(assign_state)
        if worker_id != user_id:
            continue

        state = dict(row)
        state["firm_id"] = firm_id
        state["firm_name"] = firm_name
        state["worker_id"] = worker_id
        state["assigned_by"] = _norm_text(assign_state.get("assigned_by"))
        state["withholding"] = assign_state.get("withholding")
        state["dispatcher_percent_snapshot"] = assign_state.get("dispatcher_percent_snapshot")
        state["work_type"] = assign_state.get("work_type")
        state["event_at"] = assign_state.get("event_at")
        if not state.get("start_at") and assign_state.get("start_at"):
            state["start_at"] = assign_state.get("start_at")
        if not state.get("deadline_at") and assign_state.get("deadline_at"):
            state["deadline_at"] = assign_state.get("deadline_at")

        shifts.append(
            {
                "event_id": shift_id,
                "firm_id": firm_id,
                "firm_name": firm_name,
                "state": state,
            }
        )

    deals: List[dict] = []
    for row in deals_rows:
        deal_id = _norm_text(row.get("deal_id"))
        if not deal_id:
            continue
        assign_state = latest_deal_state.get(deal_id)
        if not isinstance(assign_state, dict):
            continue
        worker_id = extract_user_id(assign_state)
        if worker_id != user_id:
            continue

        state = dict(row)
        state["firm_id"] = firm_id
        state["firm_name"] = firm_name
        state["worker_id"] = worker_id
        state["assigned_by"] = _norm_text(assign_state.get("assigned_by"))
        state["withholding"] = assign_state.get("withholding")
        state["work_type"] = assign_state.get("work_type")
        state["event_at"] = assign_state.get("event_at")
        if not state.get("start_at") and assign_state.get("start_at"):
            state["start_at"] = assign_state.get("start_at")
        if not state.get("deadline_at") and assign_state.get("deadline_at"):
            state["deadline_at"] = assign_state.get("deadline_at")

        deals.append(
            {
                "event_id": deal_id,
                "firm_id": firm_id,
                "firm_name": firm_name,
                "state": state,
            }
        )

    return shifts, deals


def handle_worker_month_deals_and_shifts(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.worker.month_work.start", firm_id=firm_id, caller_user_id=caller_user_id)

    month = body.get("month")
    year = body.get("year")
    if not isinstance(month, int) or month < 1 or month > 12:
        return bad_request("month must be an integer between 1 and 12")
    if not isinstance(year, int) or year < 2020 or year > 2100:
        return bad_request("year must be an integer between 2020 and 2100")

    body_user_id = body.get("user_id")
    if body_user_id is not None and str(body_user_id) != caller_user_id:
        return forbidden("Forbidden")

    start, end = _month_range(year=year, month=month)

    event_ids = _read_event_ids(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        table_name="object_events",
        event_types=["shift_assign", "deal_assign"],
        start=start,
        end=end,
    )

    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    shifts: List[dict] = []
    deals: List[dict] = []
    for eid, state in states.items():
        worker_id = extract_user_id(state)
        if worker_id != caller_user_id:
            continue
        if isinstance(state, dict) and state.get("shift_id"):
            shifts.append({"event_id": eid, "state": state})
        elif isinstance(state, dict) and state.get("deal_id"):
            deals.append({"event_id": eid, "state": state})

    logger.info(
        "analytics_getter.worker.month_work.success",
        firm_id=firm_id,
        caller_user_id=caller_user_id,
        year=year,
        month=month,
        shifts_count=len(shifts),
        deals_count=len(deals),
    )

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "year": year,
            "month": month,
            "shifts": shifts,
            "deals": deals,
        }
    )


def handle_worker_day_deals_and_shifts_all_firms(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info(
        "analytics_getter.worker.day_work_all_firms.start",
        context_firm_id=firm_id,
        caller_user_id=caller_user_id,
    )

    body_user_id = body.get("user_id")
    if body_user_id is not None and str(body_user_id) != caller_user_id:
        return forbidden("Forbidden")

    date_value = body.get("date")
    if not isinstance(date_value, str) or not date_value.strip():
        return bad_request("date is required in YYYY-MM-DD format")
    date_value = date_value.strip()
    try:
        start, end = _day_range(date_value=date_value)
    except Exception:
        return bad_request("date must be in YYYY-MM-DD format")

    memberships = _read_worker_memberships_all_firms(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_id=caller_user_id,
    )
    if not memberships:
        return forbidden("Forbidden")

    all_shifts: List[dict] = []
    all_deals: List[dict] = []
    firms_summary: List[dict] = []
    firms_with_events_count = 0

    for membership in memberships:
        worker_shifts, worker_deals = _collect_worker_assignments_for_firm(
            user_id=caller_user_id,
            firm_id=membership["firm_id"],
            firm_name=membership["firm_name"],
            start=start,
            end=end,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            period_kind="day",
            logger=logger,
        )
        if worker_shifts or worker_deals:
            firms_with_events_count += 1

        firms_summary.append(
            {
                "firm_id": membership["firm_id"],
                "firm_name": membership["firm_name"],
                "role_type": membership["role_type"],
                "employee_status": membership["employee_status"],
                "shifts": worker_shifts,
                "deals": worker_deals,
            }
        )
        all_shifts.extend(worker_shifts)
        all_deals.extend(worker_deals)

    logger.info(
        "analytics_getter.worker.day_work_all_firms.success",
        caller_user_id=caller_user_id,
        date=date_value,
        firms_count=len(firms_summary),
        firms_with_events_count=firms_with_events_count,
        shifts_count=len(all_shifts),
        deals_count=len(all_deals),
    )
    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "date": date_value,
            "firms_count": len(firms_summary),
            "firms_with_events_count": firms_with_events_count,
            "shifts": all_shifts,
            "deals": all_deals,
            "firms": firms_summary,
        }
    )


def handle_worker_month_deals_and_shifts_all_firms(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info(
        "analytics_getter.worker.month_work_all_firms.start",
        context_firm_id=firm_id,
        caller_user_id=caller_user_id,
    )

    body_user_id = body.get("user_id")
    if body_user_id is not None and str(body_user_id) != caller_user_id:
        return forbidden("Forbidden")

    month = body.get("month")
    year = body.get("year")
    if not isinstance(month, int) or month < 1 or month > 12:
        return bad_request("month must be an integer between 1 and 12")
    if not isinstance(year, int) or year < 2020 or year > 2100:
        return bad_request("year must be an integer between 2020 and 2100")
    start, end = _month_range(year=year, month=month)

    memberships = _read_worker_memberships_all_firms(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_id=caller_user_id,
    )
    if not memberships:
        return forbidden("Forbidden")

    all_shifts: List[dict] = []
    all_deals: List[dict] = []
    firms_summary: List[dict] = []
    firms_with_events_count = 0

    for membership in memberships:
        worker_shifts, worker_deals = _collect_worker_assignments_for_firm(
            user_id=caller_user_id,
            firm_id=membership["firm_id"],
            firm_name=membership["firm_name"],
            start=start,
            end=end,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            period_kind="month",
            logger=logger,
        )
        if worker_shifts or worker_deals:
            firms_with_events_count += 1

        firms_summary.append(
            {
                "firm_id": membership["firm_id"],
                "firm_name": membership["firm_name"],
                "role_type": membership["role_type"],
                "employee_status": membership["employee_status"],
                "shifts": worker_shifts,
                "deals": worker_deals,
            }
        )
        all_shifts.extend(worker_shifts)
        all_deals.extend(worker_deals)

    logger.info(
        "analytics_getter.worker.month_work_all_firms.success",
        caller_user_id=caller_user_id,
        year=year,
        month=month,
        firms_count=len(firms_summary),
        firms_with_events_count=firms_with_events_count,
        shifts_count=len(all_shifts),
        deals_count=len(all_deals),
    )
    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "year": year,
            "month": month,
            "firms_count": len(firms_summary),
            "firms_with_events_count": firms_with_events_count,
            "shifts": all_shifts,
            "deals": all_deals,
            "firms": firms_summary,
        }
    )


def handle_worker_fines_year_total(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    year = body.get("year")
    if not isinstance(year, int) or year < 2020 or year > 2100:
        return bad_request("year must be an integer between 2020 and 2100")

    start, end = _year_range(year=year)
    event_ids = _read_event_ids(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        table_name="finance_events",
        event_types=[EVENT_TYPE_FINE],
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    total_kopeks = 0
    matched_events = 0
    for state in states.values():
        uid = extract_user_id(state)
        if uid != caller_user_id:
            continue
        amount = extract_amount_kopeks(state)
        if isinstance(amount, int):
            total_kopeks += amount
            matched_events += 1

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "year": year,
            "fine_total_kopeks": total_kopeks,
            "events_count": matched_events,
        }
    )


def handle_worker_fines_month_list(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    month = body.get("month")
    year = body.get("year")
    if not isinstance(month, int) or month < 1 or month > 12:
        return bad_request("month must be an integer between 1 and 12")
    if not isinstance(year, int) or year < 2020 or year > 2100:
        return bad_request("year must be an integer between 2020 and 2100")

    start, end = _month_range(year=year, month=month)
    event_ids = _read_event_ids(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        table_name="finance_events",
        event_types=[EVENT_TYPE_FINE],
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    fines: List[dict] = []
    for eid, state in states.items():
        uid = extract_user_id(state)
        if uid != caller_user_id:
            continue
        fines.append({"event_id": eid, "state": state})

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "year": year,
            "month": month,
            "fines": fines,
        }
    )


def handle_worker_fines_year_list_excluding_month(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    month = body.get("month")
    year = body.get("year")
    if not isinstance(month, int) or month < 1 or month > 12:
        return bad_request("month must be an integer between 1 and 12")
    if not isinstance(year, int) or year < 2020 or year > 2100:
        return bad_request("year must be an integer between 2020 and 2100")

    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year, month, 1, tzinfo=timezone.utc)

    event_ids = _read_event_ids(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        table_name="finance_events",
        event_types=[EVENT_TYPE_FINE],
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    fines: List[dict] = []
    for eid, state in states.items():
        uid = extract_user_id(state)
        if uid != caller_user_id:
            continue
        fines.append({"event_id": eid, "state": state})

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "year": year,
            "exclude_month": month,
            "fines": fines,
        }
    )


def _read_finance_events_for_period(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    event_types: List[str],
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        types_yql = ", ".join([f"'{t}'" for t in event_types])
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at
        FROM finance_events
        WHERE firm_id = $firm_id
          AND event_type IN ({types_yql})
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY created_at DESC, sequence_number DESC;
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
            items.append(
                {
                    "event_id": event_id,
                    "event_type": _norm_text(getattr(row, "event_type", None)),
                    "created_at": getattr(row, "created_at", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return items


def _datetime_utc_or_none(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        raw = float(value)
        abs_raw = abs(raw)
        # YDB/clients may return epoch in microseconds, milliseconds or seconds.
        if abs_raw >= 1e14:
            return datetime.fromtimestamp(raw / 1_000_000, tz=timezone.utc)
        if abs_raw >= 1e11:
            return datetime.fromtimestamp(raw / 1_000, tz=timezone.utc)
        if abs_raw >= 1e9:
            return datetime.fromtimestamp(raw, tz=timezone.utc)
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        # Numeric unix timestamp represented as string.
        try:
            as_num = float(text)
            return _datetime_utc_or_none(as_num)
        except Exception:
            pass
        # ISO-8601 string (allow trailing Z).
        try:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None
    return None


def _validate_year_month_filters(*, body: dict) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    year_raw = body.get("year")
    month_raw = body.get("month")
    if year_raw is None and month_raw is None:
        return None, None, None
    if year_raw is None and month_raw is not None:
        return None, None, "year is required when month is provided"
    if not isinstance(year_raw, int) or year_raw < 2020 or year_raw > 2100:
        return None, None, "year must be an integer between 2020 and 2100"
    if month_raw is None:
        return year_raw, None, None
    if not isinstance(month_raw, int) or month_raw < 1 or month_raw > 12:
        return None, None, "month must be an integer between 1 and 12"
    return year_raw, month_raw, None


def _build_worker_fines_for_firm(
    *,
    user_id: str,
    firm_id: str,
    firm_name: str,
    employee_status: str,
    start: datetime,
    end: datetime,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
) -> List[Dict[str, Any]]:
    finance_rows = _read_finance_events_for_period(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        event_types=[EVENT_TYPE_FINE, EVENT_TYPE_FINE.lower()],
        start=start,
        end=end,
    )
    if not finance_rows:
        return []

    event_ids = [x["event_id"] for x in finance_rows if isinstance(x.get("event_id"), str)]
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    out: List[Dict[str, Any]] = []
    for row in finance_rows:
        event_id = row.get("event_id")
        if not event_id:
            continue
        state = states.get(event_id)
        event_user_id = extract_user_id(state)
        if event_user_id != user_id:
            continue
        amount_kopeks = extract_amount_kopeks(state)
        object_id = _norm_text(state.get("object_id")) if isinstance(state, dict) else ""
        created_at_dt = _datetime_utc_or_none(row.get("created_at"))
        out.append(
            {
                "event_id": event_id,
                "event_type": _norm_text(row.get("event_type")) or EVENT_TYPE_FINE,
                "created_at": _to_iso_utc(created_at_dt or row.get("created_at")),
                "_created_at_dt": created_at_dt,
                "amount_kopeks": amount_kopeks if isinstance(amount_kopeks, int) else 0,
                "theme": _norm_text(state.get("theme")) if isinstance(state, dict) else "",
                "message": _norm_text(state.get("message")) if isinstance(state, dict) else "",
                "object_id": object_id or None,
                "state": state if isinstance(state, dict) else {},
                "firm": {
                    "firm_id": firm_id,
                    "firm_name": firm_name,
                    "employee_status": employee_status,
                },
            }
        )
    return out


def _read_absence_events_for_period(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type IN ('{EVENT_TYPE_ABSENCE}', '{EVENT_TYPE_ABSENCE.upper()}')
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY created_at DESC, sequence_number DESC;
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
            items.append(
                {
                    "event_id": event_id,
                    "event_type": _norm_text(getattr(row, "event_type", None)),
                    "created_at": getattr(row, "created_at", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return items


def _extract_object_id_from_state(state: Any) -> Optional[str]:
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


def _extract_object_address_from_state(state: Any) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in ("object_address", "object_full_address", "address"):
        value = _norm_text(state.get(key))
        if value:
            return value
    obj_block = state.get("object")
    if isinstance(obj_block, dict):
        for key in ("address", "full_address_text"):
            value = _norm_text(obj_block.get(key))
            if value:
                return value
    return None


def _extract_address_text(address_json: Any) -> Optional[str]:
    if isinstance(address_json, dict):
        for key in ("full_address_text", "address", "value"):
            value = _norm_text(address_json.get(key))
            if value:
                return value
    return None


def _extract_shift_moment(state: Any, *, keys: List[str]) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in keys:
        value = state.get(key)
        if value is None:
            continue
        if isinstance(value, datetime):
            return _to_iso_utc(value)
        text = _norm_text(value)
        if text:
            return text
    shift_block = state.get("shift")
    if isinstance(shift_block, dict):
        for key in keys:
            value = shift_block.get(key)
            if value is None:
                continue
            if isinstance(value, datetime):
                return _to_iso_utc(value)
            text = _norm_text(value)
            if text:
                return text
    return None


def _build_worker_absences_for_firm(
    *,
    user_id: str,
    firm_id: str,
    firm_name: str,
    employee_status: str,
    start: datetime,
    end: datetime,
    events_pool: ydb.SessionPool,
    events_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
) -> List[Dict[str, Any]]:
    event_rows = _read_absence_events_for_period(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start=start,
        end=end,
    )
    if not event_rows:
        return []

    event_ids = [x["event_id"] for x in event_rows if isinstance(x.get("event_id"), str)]
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    out: List[Dict[str, Any]] = []
    for row in event_rows:
        event_id = row.get("event_id")
        if not event_id:
            continue
        state = states.get(event_id)
        event_user_id = extract_user_id(state)
        if event_user_id != user_id:
            continue
        object_id = _extract_object_id_from_state(state)
        object_address = _extract_object_address_from_state(state)
        shift_start_at = _extract_shift_moment(
            state,
            keys=["shift_start_at", "shift_start", "start_at", "start_time"],
        )
        shift_end_at = _extract_shift_moment(
            state,
            keys=["shift_end_at", "shift_end", "end_at", "end_time"],
        )
        created_at_dt = _datetime_utc_or_none(row.get("created_at"))
        metadata = state if isinstance(state, dict) else {}
        out.append(
            {
                "event_id": event_id,
                "event_type": _norm_text(row.get("event_type")) or EVENT_TYPE_ABSENCE,
                "created_at": _to_iso_utc(created_at_dt or row.get("created_at")),
                "_created_at_dt": created_at_dt,
                "metadata": metadata,
                "object_id": object_id or None,
                "object_address": object_address or None,
                "shift_start_at": shift_start_at,
                "shift_end_at": shift_end_at,
                "firm": {
                    "firm_id": firm_id,
                    "firm_name": firm_name,
                    "employee_status": employee_status,
                },
            }
        )
    return out


def _read_objects_by_ids(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    object_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    if not object_ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
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
                    "object_name": _norm_text(getattr(row, "object_name", None)),
                    "status": _norm_text(getattr(row, "status", None)),
                    "address_json": address if isinstance(address, dict) else address,
                }

        objects_pool.retry_operation_sync(_tx)

    return out


def _read_fine_disputes_by_event_ids(
    *,
    appeals_pool: ydb.SessionPool,
    appeals_database: str,
    firm_id: str,
    event_ids: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    if not event_ids:
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
                item = {
                    "appeal_id": _norm_text(getattr(row, "appeal_id", None)),
                    "status": _norm_text(getattr(row, "status", None)),
                    "user_id": _norm_text(getattr(row, "user_id", None)),
                    "object_id": _norm_text(getattr(row, "object_id", None)) or None,
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }
                out.setdefault(source_event_id, []).append(item)

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


def _read_absence_disputes_by_event_ids(
    *,
    appeals_pool: ydb.SessionPool,
    appeals_database: str,
    firm_id: str,
    user_id: str,
    event_ids: List[str],
) -> Dict[str, List[Dict[str, Any]]]:
    if not event_ids:
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

    normalized_user_id = _norm_text(user_id)
    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{appeals_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $source_type AS Utf8;
            DECLARE $source_event_ids AS List<Utf8>;
            SELECT appeal_id, status, user_id, created_at, updated_at, object_id, deal_id
            FROM Appeals
            WHERE firm_id = $firm_id
              AND user_id = $user_id
              AND shift_id = $source_type
              AND deal_id IN $source_event_ids
            ORDER BY created_at DESC;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {
                    "$firm_id": firm_id,
                    "$user_id": normalized_user_id,
                    "$source_type": "absence",
                    "$source_event_ids": chunk,
                },
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                source_event_id = _norm_text(getattr(row, "deal_id", None))
                if not source_event_id:
                    continue
                status = _norm_text(getattr(row, "status", None))
                item = {
                    "appeal_id": _norm_text(getattr(row, "appeal_id", None)),
                    "status": status,
                    "is_closed": status.lower() in {"closed", "closed_unprocessed"},
                    "user_id": _norm_text(getattr(row, "user_id", None)),
                    "object_id": _norm_text(getattr(row, "object_id", None)) or None,
                    "source_event_id": source_event_id,
                    "source_type": "absence",
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }
                out.setdefault(source_event_id, []).append(item)

        appeals_pool.retry_operation_sync(_tx)

    return out


def _to_absence_dispute_summary(disputes: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = disputes if isinstance(disputes, list) else []
    latest = items[0] if items else None
    return {
        "has_dispute": len(items) > 0,
        "disputes_count": len(items),
        "latest_dispute": latest,
    }


from handlers_worker_home_all_firms import (
    handle_worker_fines_totals_all_firms,
    handle_worker_fines_list_all_firms,
    handle_worker_absences_list_all_firms,
)