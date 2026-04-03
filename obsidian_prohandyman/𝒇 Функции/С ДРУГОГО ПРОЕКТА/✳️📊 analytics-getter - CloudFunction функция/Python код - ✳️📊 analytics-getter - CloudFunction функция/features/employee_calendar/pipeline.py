# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from event_state import fetch_firm_event_states

from .queries import (
    fetch_assign_event_rows_before,
    fetch_deal_rows_for_day,
    fetch_object_rows_by_ids,
    fetch_shift_rows_for_day,
    fetch_user_profiles_map,
)
from .shared import norm_str, to_datetime_utc, to_iso_utc


UPCOMING_SHIFT_STATUSES = {"pending", "active"}
UPCOMING_DEAL_STATUSES = {"active"}
PERIOD_SHIFT_STATUSES = {
    "cancelled",
    "completed",
    "force_cancelled",
    "force_completed",
    "rejected",
}
PERIOD_DEAL_STATUSES = {
    "archived",
    "cancelled",
    "completed",
    "force_cancelled",
    "force_completed",
    "rejected",
}


def _row_sort_dt(row: Dict[str, Any], *, is_shift: bool):
    nested = row.get("shift") if is_shift else row.get("deal")
    nested = nested if isinstance(nested, dict) else {}
    for key in ("closed_at", "updated_at", "deadline_at", "start_at", "created_at"):
        dt = to_datetime_utc(nested.get(key))
        if dt is not None:
            return dt
    return to_datetime_utc(row.get("created_at"))


def _is_within_day(dt, *, window_start, window_end) -> bool:
    return dt is not None and window_start <= dt < window_end


def _is_not_before_day_end(dt, *, window_start) -> bool:
    return dt is None or dt >= window_start


def _is_upcoming_shift_for_day(
    row: Dict[str, Any],
    *,
    window_start,
    window_end,
) -> bool:
    nested = row.get("shift")
    nested = nested if isinstance(nested, dict) else {}

    if norm_str(nested.get("status")).lower() not in UPCOMING_SHIFT_STATUSES:
        return False
    if norm_str(nested.get("object_status")).lower() == "archived":
        return False

    scheduled_start_at = to_datetime_utc(nested.get("start_at"))
    opened_at = to_datetime_utc(nested.get("opened_at"))
    deadline_at = to_datetime_utc(nested.get("deadline_at"))
    closed_at = to_datetime_utc(nested.get("closed_at"))
    created_at = to_datetime_utc(nested.get("created_at")) or to_datetime_utc(
        row.get("created_at")
    )

    effective_start_at = scheduled_start_at or opened_at
    effective_end_at = deadline_at or closed_at

    if effective_start_at is not None:
        return effective_start_at < window_end and _is_not_before_day_end(
            effective_end_at, window_start=window_start
        )

    return _is_within_day(created_at, window_start=window_start, window_end=window_end)


def _is_upcoming_deal_for_day(
    row: Dict[str, Any],
    *,
    window_start,
    window_end,
) -> bool:
    nested = row.get("deal")
    nested = nested if isinstance(nested, dict) else {}

    if norm_str(nested.get("status")).lower() not in UPCOMING_DEAL_STATUSES:
        return False
    if norm_str(nested.get("object_status")).lower() == "archived":
        return False

    start_at = to_datetime_utc(nested.get("start_at"))
    deadline_at = to_datetime_utc(nested.get("deadline_at"))
    created_at = to_datetime_utc(nested.get("created_at")) or to_datetime_utc(
        row.get("created_at")
    )

    if start_at is not None:
        return start_at < window_end and _is_not_before_day_end(
            deadline_at, window_start=window_start
        )

    if deadline_at is not None:
        return _is_within_day(
            deadline_at, window_start=window_start, window_end=window_end
        )

    return _is_within_day(created_at, window_start=window_start, window_end=window_end)


def _build_latest_assign_states(
    *,
    firm_id: str,
    shift_ids: List[str],
    deal_ids: List[str],
    end_at,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    shift_set = {sid for sid in (norm_str(value) for value in shift_ids) if sid}
    deal_set = {did for did in (norm_str(value) for value in deal_ids) if did}
    if not shift_set and not deal_set:
        return {}, {}

    assign_rows = fetch_assign_event_rows_before(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        end_at=end_at,
    )
    event_ids = [row["event_id"] for row in assign_rows if row.get("event_id")]
    if not event_ids:
        return {}, {}

    states_by_event_id = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    latest_shift_state: Dict[str, Dict[str, Any]] = {}
    latest_deal_state: Dict[str, Dict[str, Any]] = {}

    for row in assign_rows:
        event_id = norm_str(row.get("event_id"))
        if not event_id:
            continue
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue

        shift_id = norm_str(state.get("shift_id"))
        if shift_id and shift_id in shift_set:
            latest_shift_state[shift_id] = state

        deal_id = norm_str(state.get("deal_id"))
        if deal_id and deal_id in deal_set:
            latest_deal_state[deal_id] = state

    return latest_shift_state, latest_deal_state


def _enrich_row_from_state(row: Dict[str, Any], state: Dict[str, Any], *, is_shift: bool) -> None:
    row["withholding"] = state.get("withholding")
    row["dispatcher_percent_snapshot"] = state.get("dispatcher_percent_snapshot")
    row["work_type"] = state.get("work_type")
    row["worker_id"] = norm_str(
        state.get("worker_id")
        or state.get("worker_user_id")
        or state.get("user_id")
        or state.get("employee_id")
    )
    row["assigned_by"] = norm_str(state.get("assigned_by"))
    row["event_at"] = state.get("event_at")

    nested_key = "shift" if is_shift else "deal"
    nested = row.get(nested_key)
    if not isinstance(nested, dict):
        return
    if not nested.get("start_at") and state.get("start_at") is not None:
        nested["start_at"] = state.get("start_at")
    if not nested.get("deadline_at") and state.get("deadline_at") is not None:
        nested["deadline_at"] = state.get("deadline_at")
    if is_shift and not nested.get("closed_at") and state.get("end_at") is not None:
        nested["closed_at"] = state.get("end_at")


def _attach_object_info(row: Dict[str, Any], object_row: Optional[Dict[str, Any]], *, is_shift: bool) -> None:
    if not isinstance(object_row, dict):
        return
    nested_key = "shift" if is_shift else "deal"
    nested = row.get(nested_key)
    if not isinstance(nested, dict):
        return
    nested["object_name"] = object_row.get("object_name")
    nested["address_json"] = object_row.get("address_json")
    nested["object_status"] = object_row.get("status")


def _serialize_rows(rows: List[Dict[str, Any]], *, is_shift: bool) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    nested_key = "shift" if is_shift else "deal"

    for row in rows:
        nested = row.get(nested_key)
        if not isinstance(nested, dict):
            continue
        item = dict(row)
        item["created_at"] = to_iso_utc(row.get("created_at"))
        item["event_at"] = to_iso_utc(row.get("event_at"))
        item[nested_key] = {
            **nested,
            "deadline_at": to_iso_utc(nested.get("deadline_at")),
            "start_at": to_iso_utc(nested.get("start_at")),
            "opened_at": to_iso_utc(nested.get("opened_at")),
            "closed_at": to_iso_utc(nested.get("closed_at")),
            "created_at": to_iso_utc(nested.get("created_at")),
            "updated_at": to_iso_utc(nested.get("updated_at")),
        }
        serialized.append(item)

    return serialized


def _log_rows_preview(rows: List[Dict[str, Any]], *, is_shift: bool) -> List[Dict[str, Any]]:
    nested_key = "shift" if is_shift else "deal"
    id_key = "shift_id" if is_shift else "deal_id"
    preview: List[Dict[str, Any]] = []
    for row in rows[:20]:
        nested = row.get(nested_key)
        nested = nested if isinstance(nested, dict) else {}
        preview.append(
            {
                id_key: norm_str(row.get(id_key)),
                "worker_id": norm_str(row.get("worker_id")),
                "assigned_by": norm_str(row.get("assigned_by")),
                "object_id": norm_str(nested.get("object_id")),
                "status": norm_str(nested.get("status")).lower(),
                "start_at": to_iso_utc(nested.get("start_at")),
                "deadline_at": to_iso_utc(nested.get("deadline_at")),
                "opened_at": to_iso_utc(nested.get("opened_at")),
                "closed_at": to_iso_utc(nested.get("closed_at")),
                "updated_at": to_iso_utc(nested.get("updated_at")),
            }
        )
    return preview


def build_employee_calendar_day_dataset(
    *,
    firm_id: str,
    user_id: str,
    date_str: str,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    object_id: Optional[str] = None,
) -> Dict[str, Any]:
    from .shared import parse_day_window_utc

    window_start, window_end = parse_day_window_utc(date_str)

    shift_rows = fetch_shift_rows_for_day(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        start_at=window_start,
        end_at=window_end,
        object_id=object_id,
    )
    deal_rows = fetch_deal_rows_for_day(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        start_at=window_start,
        end_at=window_end,
        object_id=object_id,
    )

    shift_ids = [row.get("shift_id") for row in shift_rows if row.get("shift_id")]
    deal_ids = [row.get("deal_id") for row in deal_rows if row.get("deal_id")]

    latest_shift_state, latest_deal_state = _build_latest_assign_states(
        firm_id=firm_id,
        shift_ids=shift_ids,
        deal_ids=deal_ids,
        end_at=window_end,
        events_pool=events_pool,
        events_database=events_database,
        meta_pool=meta_pool,
        meta_database=meta_database,
        logger=logger,
    )

    matched_shift_rows: List[Dict[str, Any]] = []
    matched_deal_rows: List[Dict[str, Any]] = []
    user_ids: List[str] = [user_id]
    object_ids: List[str] = []

    for row in shift_rows:
        shift_id = norm_str(row.get("shift_id"))
        state = latest_shift_state.get(shift_id)
        if not isinstance(state, dict):
            continue
        _enrich_row_from_state(row, state, is_shift=True)
        if norm_str(row.get("worker_id")) != user_id:
            continue
        object_ids.append(norm_str(row.get("shift", {}).get("object_id")))
        if norm_str(row.get("assigned_by")):
            user_ids.append(norm_str(row.get("assigned_by")))
        matched_shift_rows.append(row)

    for row in deal_rows:
        deal_id = norm_str(row.get("deal_id"))
        state = latest_deal_state.get(deal_id)
        if not isinstance(state, dict):
            continue
        _enrich_row_from_state(row, state, is_shift=False)
        if norm_str(row.get("worker_id")) != user_id:
            continue
        object_ids.append(norm_str(row.get("deal", {}).get("object_id")))
        if norm_str(row.get("assigned_by")):
            user_ids.append(norm_str(row.get("assigned_by")))
        matched_deal_rows.append(row)

    object_rows = fetch_object_rows_by_ids(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        object_ids=object_ids,
    )
    object_by_id = {
        norm_str(row.get("object_id")): row for row in object_rows if norm_str(row.get("object_id"))
    }

    for row in matched_shift_rows:
        shift = row.get("shift")
        object_row = object_by_id.get(norm_str(shift.get("object_id")) if isinstance(shift, dict) else "")
        _attach_object_info(row, object_row, is_shift=True)

    for row in matched_deal_rows:
        deal = row.get("deal")
        object_row = object_by_id.get(norm_str(deal.get("object_id")) if isinstance(deal, dict) else "")
        _attach_object_info(row, object_row, is_shift=False)

    profiles_by_id = fetch_user_profiles_map(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_ids=user_ids,
    )
    for row in matched_shift_rows:
        worker_id = norm_str(row.get("worker_id"))
        assigned_by = norm_str(row.get("assigned_by"))
        row["worker_profile"] = profiles_by_id.get(worker_id) if worker_id else None
        row["assigned_by_profile"] = profiles_by_id.get(assigned_by) if assigned_by else None

    for row in matched_deal_rows:
        worker_id = norm_str(row.get("worker_id"))
        assigned_by = norm_str(row.get("assigned_by"))
        row["worker_profile"] = profiles_by_id.get(worker_id) if worker_id else None
        row["assigned_by_profile"] = profiles_by_id.get(assigned_by) if assigned_by else None

    upcoming_shifts = [
        row
        for row in matched_shift_rows
        if _is_upcoming_shift_for_day(
            row,
            window_start=window_start,
            window_end=window_end,
        )
    ]
    upcoming_deals = [
        row
        for row in matched_deal_rows
        if _is_upcoming_deal_for_day(
            row,
            window_start=window_start,
            window_end=window_end,
        )
    ]
    period_shifts = [
        row
        for row in matched_shift_rows
        if norm_str(row.get("shift", {}).get("status")).lower() in PERIOD_SHIFT_STATUSES
    ]
    period_deals = [
        row
        for row in matched_deal_rows
        if norm_str(row.get("deal", {}).get("status")).lower() in PERIOD_DEAL_STATUSES
    ]

    upcoming_shifts.sort(key=lambda row: _row_sort_dt(row, is_shift=True) or window_start)
    upcoming_deals.sort(key=lambda row: _row_sort_dt(row, is_shift=False) or window_start)
    period_shifts.sort(key=lambda row: _row_sort_dt(row, is_shift=True) or window_start, reverse=True)
    period_deals.sort(key=lambda row: _row_sort_dt(row, is_shift=False) or window_start, reverse=True)

    logger.info(
        "analytics_getter.employee_calendar.dataset_built",
        user_id=user_id,
        date=date_str,
        shift_rows_count=len(shift_rows),
        deal_rows_count=len(deal_rows),
        matched_shifts_count=len(matched_shift_rows),
        matched_deals_count=len(matched_deal_rows),
        upcoming_shifts_count=len(upcoming_shifts),
        upcoming_deals_count=len(upcoming_deals),
        period_shifts_count=len(period_shifts),
        period_deals_count=len(period_deals),
        upcoming_shifts_preview=_log_rows_preview(upcoming_shifts, is_shift=True),
        upcoming_deals_preview=_log_rows_preview(upcoming_deals, is_shift=False),
    )

    return {
        "firm_id": firm_id,
        "user_id": user_id,
        "date": date_str,
        "selected_object_id": norm_str(object_id) or None,
        "upcoming": {
            "shifts": _serialize_rows(upcoming_shifts, is_shift=True),
            "deals": _serialize_rows(upcoming_deals, is_shift=False),
        },
        "period": {
            "shifts": _serialize_rows(period_shifts, is_shift=True),
            "deals": _serialize_rows(period_deals, is_shift=False),
        },
        "user_profiles": profiles_by_id,
    }
