# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from event_state import fetch_firm_event_states

from .queries import (
    fetch_assign_event_rows_before,
    fetch_deal_rows_for_window,
    fetch_object_event_rows_for_window,
    fetch_object_rows_by_ids,
    fetch_shift_rows_for_window,
)
from .shared import (
    add_interval_breakdown,
    hours_from_seconds,
    interval_payload,
    norm_str,
    overlap_range_seconds,
    safe_int,
    to_datetime_utc,
    to_iso_utc,
    unique_preserve_order,
)


LOOKBACK_24H = timedelta(hours=24)
MAX_ATTENDANCE_INTERVAL = timedelta(hours=24)
SHIFT_TERMINAL_EVENT_TYPES = {"shift_end", "shift_cancel", "shift_refuse"}
DEAL_TERMINAL_EVENT_TYPES = {
    "deal_complete",
    "deal_force_end",
    "deal_cancel",
    "deal_refuse",
}
SHIFT_PLANNED_STATUSES = {"pending", "active", "completed", "force_completed"}
DEAL_PLANNED_STATUSES = {"active", "completed", "force_completed", "archived"}


def _state_dict(states_by_event_id: Dict[str, dict], event_id: str) -> Optional[dict]:
    state = states_by_event_id.get(norm_str(event_id))
    return state if isinstance(state, dict) else None


def _event_moment(state: dict, row: Dict[str, Any]) -> Optional[datetime]:
    dt = to_datetime_utc(state.get("event_at")) if isinstance(state, dict) else None
    if dt is not None:
        return dt
    return to_datetime_utc(row.get("created_at"))


def _history_entry(
    *,
    entity_id: str,
    worker_id: str,
    object_id: str,
    event_id: str,
    event_type: str,
    sequence_number: int,
    event_at: Optional[datetime],
) -> Dict[str, Any]:
    return {
        "entity_id": entity_id,
        "worker_id": worker_id,
        "object_id": object_id,
        "event_id": event_id,
        "event_type": event_type,
        "sequence_number": sequence_number,
        "event_at": event_at,
    }


def _build_assignment_histories(
    *,
    assign_event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
    logger,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    shift_histories: Dict[str, List[Dict[str, Any]]] = {}
    deal_histories: Dict[str, List[Dict[str, Any]]] = {}

    for row in assign_event_rows:
        event_id = norm_str(row.get("event_id"))
        event_type = norm_str(row.get("event_type")).lower()
        state = _state_dict(states_by_event_id, event_id)
        if state is None:
            logger.warn(
                "analytics_getter.employee_attendance.assign_state_missing",
                event_id=event_id,
                event_type=event_type,
            )
            continue

        event_at = _event_moment(state, row)
        sequence_number = safe_int(row.get("sequence_number"))

        if event_type == "shift_assign":
            shift_id = norm_str(state.get("shift_id"))
            worker_id = norm_str(state.get("worker_id"))
            object_id = norm_str(state.get("object_id"))
            if not shift_id or not worker_id:
                logger.warn(
                    "analytics_getter.employee_attendance.invalid_shift_assign_state",
                    event_id=event_id,
                    shift_id=shift_id,
                    worker_id=worker_id,
                )
                continue
            shift_histories.setdefault(shift_id, []).append(
                _history_entry(
                    entity_id=shift_id,
                    worker_id=worker_id,
                    object_id=object_id,
                    event_id=event_id,
                    event_type=event_type,
                    sequence_number=sequence_number,
                    event_at=event_at,
                )
            )
            continue

        if event_type == "deal_assign":
            deal_id = norm_str(state.get("deal_id"))
            worker_id = norm_str(state.get("worker_id"))
            object_id = norm_str(state.get("object_id"))
            if not deal_id or not worker_id:
                logger.warn(
                    "analytics_getter.employee_attendance.invalid_deal_assign_state",
                    event_id=event_id,
                    deal_id=deal_id,
                    worker_id=worker_id,
                )
                continue
            deal_histories.setdefault(deal_id, []).append(
                _history_entry(
                    entity_id=deal_id,
                    worker_id=worker_id,
                    object_id=object_id,
                    event_id=event_id,
                    event_type=event_type,
                    sequence_number=sequence_number,
                    event_at=event_at,
                )
            )

    for history in shift_histories.values():
        history.sort(
            key=lambda item: (
                safe_int(item.get("sequence_number")),
                item.get("event_at") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            )
        )
    for history in deal_histories.values():
        history.sort(
            key=lambda item: (
                safe_int(item.get("sequence_number")),
                item.get("event_at") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            )
        )

    return shift_histories, deal_histories


def _assignment_at_time(
    history: List[Dict[str, Any]],
    point_in_time: Optional[datetime],
) -> Optional[Dict[str, Any]]:
    if not history:
        return None
    if point_in_time is None:
        return history[-1]
    matched: Optional[Dict[str, Any]] = None
    for item in history:
        event_at = item.get("event_at")
        if isinstance(event_at, datetime) and event_at <= point_in_time:
            matched = item
        elif isinstance(event_at, datetime) and event_at > point_in_time:
            break
    return matched or history[-1]


def _assignment_at_sequence(
    history: List[Dict[str, Any]],
    sequence_number: int,
) -> Optional[Dict[str, Any]]:
    if not history:
        return None
    matched: Optional[Dict[str, Any]] = None
    for item in history:
        if safe_int(item.get("sequence_number")) <= sequence_number:
            matched = item
        else:
            break
    return matched or history[-1]


def _row_reference_time(row: Dict[str, Any]) -> Optional[datetime]:
    for key in (
        "opened_at",
        "closed_at",
        "start_at",
        "deadline_at",
        "updated_at",
        "created_at",
    ):
        dt = to_datetime_utc(row.get(key))
        if dt is not None:
            return dt
    return None


def _filter_shift_rows_for_user(
    *,
    shift_rows: List[Dict[str, Any]],
    shift_histories: Dict[str, List[Dict[str, Any]]],
    user_id: str,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in shift_rows:
        shift_id = norm_str(row.get("shift_id"))
        history = shift_histories.get(shift_id, [])
        assignment = _assignment_at_time(history, _row_reference_time(row))
        if not assignment or norm_str(assignment.get("worker_id")) != user_id:
            continue
        enriched = dict(row)
        enriched["worker_id"] = user_id
        enriched["assign_event_id"] = assignment.get("event_id")
        enriched["assign_event_at"] = assignment.get("event_at")
        if not norm_str(enriched.get("object_id")):
            enriched["object_id"] = norm_str(assignment.get("object_id"))
        result.append(enriched)
    return result


def _filter_deal_rows_for_user(
    *,
    deal_rows: List[Dict[str, Any]],
    deal_histories: Dict[str, List[Dict[str, Any]]],
    user_id: str,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for row in deal_rows:
        deal_id = norm_str(row.get("deal_id"))
        history = deal_histories.get(deal_id, [])
        assignment = _assignment_at_time(history, _row_reference_time(row))
        if not assignment or norm_str(assignment.get("worker_id")) != user_id:
            continue
        enriched = dict(row)
        enriched["worker_id"] = user_id
        enriched["assign_event_id"] = assignment.get("event_id")
        enriched["assign_event_at"] = assignment.get("event_at")
        if not norm_str(enriched.get("object_id")):
            enriched["object_id"] = norm_str(assignment.get("object_id"))
        result.append(enriched)
    return result


def _shift_terminal_variant(state: dict) -> str:
    status = norm_str(state.get("status")).lower()
    if norm_str(state.get("force_ended_by")):
        return "shift_force_end"
    if status in {"force_completed", "force_cancelled"}:
        return "shift_force_end"
    return "shift_end"


def _normalize_target_user_events(
    *,
    event_rows: List[Dict[str, Any]],
    states_by_event_id: Dict[str, dict],
    shift_histories: Dict[str, List[Dict[str, Any]]],
    deal_histories: Dict[str, List[Dict[str, Any]]],
    shift_rows_by_id: Dict[str, Dict[str, Any]],
    deal_rows_by_id: Dict[str, Dict[str, Any]],
    object_rows_by_id: Dict[str, Dict[str, Any]],
    user_id: str,
    logger,
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []

    for row in event_rows:
        event_id = norm_str(row.get("event_id"))
        event_type = norm_str(row.get("event_type")).lower()
        state = _state_dict(states_by_event_id, event_id)
        if state is None:
            logger.warn(
                "analytics_getter.employee_attendance.event_state_missing",
                event_id=event_id,
                event_type=event_type,
            )
            continue
        sequence_number = safe_int(row.get("sequence_number"))
        event_at = _event_moment(state, row)
        if event_at is None:
            continue

        payload: Optional[Dict[str, Any]] = None
        object_id = ""
        object_name = ""

        if event_type in {"obj_enter", "obj_leave"}:
            event_user_id = norm_str(state.get("user_id"))
            object_id = norm_str(state.get("object_id"))
            if event_user_id != user_id or not object_id:
                continue
            object_name = norm_str(object_rows_by_id.get(object_id, {}).get("object_name"))
            payload = {
                "event_id": event_id,
                "event_type": event_type,
                "event_at": event_at,
                "sequence_number": sequence_number,
                "object_id": object_id,
                "object_name": object_name,
                "user_id": event_user_id,
                "label": "Отметился на объекте" if event_type == "obj_enter" else "Покинул объект",
            }

        elif event_type == "shift_assign":
            shift_id = norm_str(state.get("shift_id"))
            event_user_id = norm_str(state.get("worker_id"))
            if event_user_id != user_id or not shift_id:
                continue
            shift_row = shift_rows_by_id.get(shift_id, {})
            object_id = norm_str(state.get("object_id")) or norm_str(shift_row.get("object_id"))
            object_name = norm_str(object_rows_by_id.get(object_id, {}).get("object_name"))
            payload = {
                "event_id": event_id,
                "event_type": event_type,
                "event_at": event_at,
                "sequence_number": sequence_number,
                "object_id": object_id,
                "object_name": object_name,
                "shift_id": shift_id,
                "shift_name": norm_str(state.get("shift_name")) or norm_str(shift_row.get("shift_name")),
                "label": "Назначена смена",
            }

        elif event_type in {"shift_start", "shift_end", "shift_cancel", "shift_refuse"}:
            shift_id = norm_str(state.get("shift_id"))
            if not shift_id:
                continue
            history = shift_histories.get(shift_id, [])
            assignment = _assignment_at_sequence(history, sequence_number)
            if not assignment or norm_str(assignment.get("worker_id")) != user_id:
                continue
            shift_row = shift_rows_by_id.get(shift_id, {})
            object_id = norm_str(state.get("object_id")) or norm_str(shift_row.get("object_id")) or norm_str(assignment.get("object_id"))
            object_name = norm_str(object_rows_by_id.get(object_id, {}).get("object_name"))
            resolved_type = event_type
            label = {
                "shift_start": "Начал смену",
                "shift_end": "Завершил смену",
                "shift_cancel": "Смена отменена",
                "shift_refuse": "Отказался от смены",
            }.get(event_type, "Событие смены")
            if event_type == "shift_end":
                resolved_type = _shift_terminal_variant(state)
                if resolved_type == "shift_force_end":
                    label = "Смена завершена принудительно"
            payload = {
                "event_id": event_id,
                "event_type": resolved_type,
                "event_at": event_at,
                "sequence_number": sequence_number,
                "object_id": object_id,
                "object_name": object_name,
                "shift_id": shift_id,
                "shift_name": norm_str(shift_row.get("shift_name")),
                "label": label,
            }

        elif event_type == "deal_assign":
            deal_id = norm_str(state.get("deal_id"))
            event_user_id = norm_str(state.get("worker_id"))
            if event_user_id != user_id or not deal_id:
                continue
            deal_row = deal_rows_by_id.get(deal_id, {})
            object_id = norm_str(state.get("object_id")) or norm_str(deal_row.get("object_id"))
            object_name = norm_str(object_rows_by_id.get(object_id, {}).get("object_name"))
            payload = {
                "event_id": event_id,
                "event_type": event_type,
                "event_at": event_at,
                "sequence_number": sequence_number,
                "object_id": object_id,
                "object_name": object_name,
                "deal_id": deal_id,
                "deal_name": norm_str(state.get("deal_name")) or norm_str(deal_row.get("deal_name")),
                "label": "Назначена сделка",
            }

        elif event_type in {"deal_complete", "deal_force_end", "deal_cancel", "deal_refuse"}:
            deal_id = norm_str(state.get("deal_id"))
            if not deal_id:
                continue
            history = deal_histories.get(deal_id, [])
            assignment = _assignment_at_sequence(history, sequence_number)
            if not assignment or norm_str(assignment.get("worker_id")) != user_id:
                continue
            deal_row = deal_rows_by_id.get(deal_id, {})
            object_id = norm_str(state.get("object_id")) or norm_str(deal_row.get("object_id")) or norm_str(assignment.get("object_id"))
            object_name = norm_str(object_rows_by_id.get(object_id, {}).get("object_name"))
            payload = {
                "event_id": event_id,
                "event_type": event_type,
                "event_at": event_at,
                "sequence_number": sequence_number,
                "object_id": object_id,
                "object_name": object_name,
                "deal_id": deal_id,
                "deal_name": norm_str(deal_row.get("deal_name")),
                "label": {
                    "deal_complete": "Завершил сделку",
                    "deal_force_end": "Сделка завершена принудительно",
                    "deal_cancel": "Сделка отменена",
                    "deal_refuse": "Отказался от сделки",
                }.get(event_type, "Событие сделки"),
            }

        if payload is not None:
            result.append(payload)

    result.sort(
        key=lambda item: (
            item.get("event_at") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            safe_int(item.get("sequence_number")),
        )
    )
    return result


def _build_shift_actual_intervals(
    *,
    normalized_events: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    logger,
) -> List[Dict[str, Any]]:
    intervals: List[Dict[str, Any]] = []
    open_shift_starts: Dict[str, Dict[str, Any]] = {}

    for event in normalized_events:
        event_type = norm_str(event.get("event_type")).lower()
        if event_type not in {
            "shift_start",
            "shift_end",
            "shift_force_end",
            "shift_cancel",
            "shift_refuse",
        }:
            continue

        shift_id = norm_str(event.get("shift_id"))
        object_id = norm_str(event.get("object_id"))
        event_at = event.get("event_at")
        if not shift_id or not object_id or not isinstance(event_at, datetime):
            continue

        if event_type == "shift_start":
            open_shift_starts[shift_id] = event
            continue

        shift_start_event = open_shift_starts.get(shift_id)
        if shift_start_event is None:
            continue

        started_at = shift_start_event.get("event_at")
        if not isinstance(started_at, datetime):
            open_shift_starts.pop(shift_id, None)
            continue
        if event_at - started_at > MAX_ATTENDANCE_INTERVAL:
            logger.warn(
                "analytics_getter.employee_attendance.shift_interval_skipped_too_long",
                shift_id=shift_id,
                object_id=object_id,
                started_at=started_at.isoformat(),
                ended_at=event_at.isoformat(),
                span_hours=hours_from_seconds(int((event_at - started_at).total_seconds())),
            )
            open_shift_starts.pop(shift_id, None)
            continue

        payload = interval_payload(
            object_id=norm_str(shift_start_event.get("object_id")),
            source_type="shift",
            source_id=shift_id,
            started_at=started_at,
            ended_at=event_at,
        )
        if (
            payload is not None
            and overlap_range_seconds(
                payload["started_at"],
                payload["ended_at"],
                window_start,
                window_end,
            )
            > 0
        ):
            intervals.append(payload)
        open_shift_starts.pop(shift_id, None)

    return intervals


def _build_shift_planned_intervals(
    *,
    shift_rows: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> List[Dict[str, Any]]:
    intervals: List[Dict[str, Any]] = []
    for row in shift_rows:
        status = norm_str(row.get("status")).lower()
        if status not in SHIFT_PLANNED_STATUSES:
            continue
        started_at = to_datetime_utc(row.get("start_at"))
        ended_at = to_datetime_utc(row.get("deadline_at"))
        payload = interval_payload(
            object_id=norm_str(row.get("object_id")),
            source_type="shift_planned",
            source_id=norm_str(row.get("shift_id")),
            started_at=started_at,
            ended_at=ended_at,
        )
        if payload is None:
            continue
        if overlap_range_seconds(payload["started_at"], payload["ended_at"], window_start, window_end) <= 0:
            continue
        intervals.append(payload)
    return intervals


def _build_presence_intervals_from_events(
    *,
    normalized_events: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
    logger,
) -> List[Dict[str, Any]]:
    intervals: List[Dict[str, Any]] = []
    open_presence_by_object: Dict[str, Dict[str, Any]] = {}

    for event in normalized_events:
        event_type = norm_str(event.get("event_type")).lower()
        object_id = norm_str(event.get("object_id"))
        if not object_id:
            continue
        event_at = event.get("event_at")
        if not isinstance(event_at, datetime):
            continue

        if event_type == "obj_enter":
            open_presence_by_object[object_id] = event
            continue

        if event_type in {"obj_leave"} | DEAL_TERMINAL_EVENT_TYPES:
            current = open_presence_by_object.get(object_id)
            if current is None:
                continue
            started_at = current.get("event_at")
            if not isinstance(started_at, datetime):
                open_presence_by_object.pop(object_id, None)
                continue
            if event_at - started_at > MAX_ATTENDANCE_INTERVAL:
                logger.warn(
                    "analytics_getter.employee_attendance.presence_interval_skipped_too_long",
                    object_id=object_id,
                    source_event_type=event_type,
                    started_at=started_at.isoformat(),
                    ended_at=event_at.isoformat(),
                    span_hours=hours_from_seconds(int((event_at - started_at).total_seconds())),
                )
                open_presence_by_object.pop(object_id, None)
                continue
            payload = interval_payload(
                object_id=object_id,
                source_type="deal" if event_type in DEAL_TERMINAL_EVENT_TYPES else "presence",
                source_id=norm_str(event.get("deal_id")) or norm_str(current.get("event_id")),
                started_at=started_at,
                ended_at=event_at,
            )
            if payload and overlap_range_seconds(payload["started_at"], payload["ended_at"], window_start, window_end) > 0:
                intervals.append(payload)
            open_presence_by_object.pop(object_id, None)

    return intervals


def _build_deal_planned_intervals(
    *,
    deal_rows: List[Dict[str, Any]],
    normalized_events: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> List[Dict[str, Any]]:
    intervals: List[Dict[str, Any]] = []
    enters_by_object: Dict[str, List[datetime]] = {}
    terminal_event_at_by_deal_id: Dict[str, datetime] = {}
    for event in normalized_events:
        event_type = norm_str(event.get("event_type")).lower()
        if event_type == "obj_enter":
            object_id = norm_str(event.get("object_id"))
            event_at = event.get("event_at")
            if not object_id or not isinstance(event_at, datetime):
                continue
            enters_by_object.setdefault(object_id, []).append(event_at)
            continue
        if event_type not in DEAL_TERMINAL_EVENT_TYPES:
            continue
        deal_id = norm_str(event.get("deal_id"))
        event_at = event.get("event_at")
        if not deal_id or not isinstance(event_at, datetime):
            continue
        existing = terminal_event_at_by_deal_id.get(deal_id)
        if existing is None or event_at < existing:
            terminal_event_at_by_deal_id[deal_id] = event_at

    for object_id in list(enters_by_object.keys()):
        enters_by_object[object_id].sort()

    for row in deal_rows:
        status = norm_str(row.get("status")).lower()
        if status not in DEAL_PLANNED_STATUSES:
            continue
        deal_id = norm_str(row.get("deal_id"))
        object_id = norm_str(row.get("object_id"))
        deadline_at = to_datetime_utc(row.get("deadline_at"))
        if not deal_id or not object_id or deadline_at is None:
            continue

        terminal_event_at = terminal_event_at_by_deal_id.get(deal_id)
        search_cutoff = terminal_event_at or deadline_at
        matched_enter: Optional[datetime] = None
        for enter_at in enters_by_object.get(object_id, []):
            if enter_at > search_cutoff:
                break
            if deadline_at - enter_at <= LOOKBACK_24H:
                matched_enter = enter_at
        payload = interval_payload(
            object_id=object_id,
            source_type="deal_planned",
            source_id=deal_id,
            started_at=matched_enter,
            ended_at=deadline_at,
        )
        if payload is None:
            continue
        if overlap_range_seconds(payload["started_at"], payload["ended_at"], window_start, window_end) <= 0:
            continue
        intervals.append(payload)
    return intervals


def _merge_intervals(intervals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    prepared: List[Dict[str, Any]] = []
    for interval in intervals:
        started_at = interval.get("started_at")
        ended_at = interval.get("ended_at")
        if not isinstance(started_at, datetime) or not isinstance(ended_at, datetime):
            continue
        if ended_at <= started_at:
            continue
        prepared.append(
            {
                "started_at": started_at,
                "ended_at": ended_at,
            }
        )

    prepared.sort(key=lambda item: (item["started_at"], item["ended_at"]))
    merged: List[Dict[str, Any]] = []
    for current in prepared:
        if not merged:
            merged.append(current)
            continue
        last = merged[-1]
        if current["started_at"] > last["ended_at"]:
            merged.append(current)
            continue
        if current["ended_at"] > last["ended_at"]:
            last["ended_at"] = current["ended_at"]
    return merged


def _aggregate_totals(
    *,
    actual_intervals: List[Dict[str, Any]],
    planned_intervals: List[Dict[str, Any]],
    window_start: datetime,
    window_end: datetime,
) -> Dict[str, Any]:
    actual_breakdown: Dict[str, int] = {}
    planned_breakdown: Dict[str, int] = {}
    actual_seconds = 0
    planned_seconds = 0
    actual_object_ids: List[str] = []

    merged_actual_intervals = _merge_intervals(actual_intervals)
    merged_planned_intervals = _merge_intervals(planned_intervals)

    for interval in actual_intervals:
        object_id = norm_str(interval.get("object_id"))
        if object_id:
            actual_object_ids.append(object_id)

    for interval in merged_actual_intervals:
        start = interval.get("started_at")
        end = interval.get("ended_at")
        seconds = overlap_range_seconds(start, end, window_start, window_end)
        if seconds <= 0:
            continue
        actual_seconds += seconds
        add_interval_breakdown(
            actual_breakdown,
            start=start,
            end=end,
            window_start=window_start,
            window_end=window_end,
        )
    for interval in merged_planned_intervals:
        start = interval.get("started_at")
        end = interval.get("ended_at")
        seconds = overlap_range_seconds(start, end, window_start, window_end)
        if seconds <= 0:
            continue
        planned_seconds += seconds
        add_interval_breakdown(
            planned_breakdown,
            start=start,
            end=end,
            window_start=window_start,
            window_end=window_end,
        )

    return {
        "actual_seconds": actual_seconds,
        "actual_hours": hours_from_seconds(actual_seconds),
        "planned_seconds": planned_seconds,
        "planned_hours": hours_from_seconds(planned_seconds),
        "actual_unique_object_ids": unique_preserve_order(actual_object_ids),
        "actual_breakdown": actual_breakdown,
        "planned_breakdown": planned_breakdown,
    }


def _calendar_days_payload(
    *,
    breakdown_actual: Dict[str, int],
    breakdown_planned: Dict[str, int],
    window_start: datetime,
    window_end: datetime,
) -> List[Dict[str, Any]]:
    days: List[Dict[str, Any]] = []
    cursor = window_start
    while cursor < window_end:
        key = cursor.date().isoformat()
        actual_seconds = breakdown_actual.get(key, 0)
        planned_seconds = breakdown_planned.get(key, 0)
        days.append(
            {
                "date": key,
                "actual_seconds": actual_seconds,
                "actual_hours": hours_from_seconds(actual_seconds),
                "planned_seconds": planned_seconds,
                "planned_hours": hours_from_seconds(planned_seconds),
            }
        )
        cursor += timedelta(days=1)
    return days


def build_employee_attendance_dataset(
    *,
    firm_id: str,
    user_id: str,
    window_start: datetime,
    window_end: datetime,
    objects_pool,
    objects_database: str,
    events_pool,
    events_database: str,
    meta_pool,
    meta_database: str,
    logger,
) -> Dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    event_window_start = window_start - LOOKBACK_24H

    shift_rows_raw = fetch_shift_rows_for_window(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        start_at=event_window_start,
        end_at=window_end,
    )
    deal_rows_raw = fetch_deal_rows_for_window(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        start_at=event_window_start,
        end_at=window_end,
    )
    event_rows = fetch_object_event_rows_for_window(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start_at=event_window_start,
        end_at=window_end,
    )
    assign_rows = fetch_assign_event_rows_before(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        end_at=window_end,
    )

    state_event_ids = unique_preserve_order(
        [norm_str(row.get("event_id")) for row in event_rows + assign_rows]
    )
    states_by_event_id = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=state_event_ids,
        logger=logger,
    )

    shift_histories, deal_histories = _build_assignment_histories(
        assign_event_rows=assign_rows,
        states_by_event_id=states_by_event_id,
        logger=logger,
    )

    shift_rows = _filter_shift_rows_for_user(
        shift_rows=shift_rows_raw,
        shift_histories=shift_histories,
        user_id=user_id,
    )
    deal_rows = _filter_deal_rows_for_user(
        deal_rows=deal_rows_raw,
        deal_histories=deal_histories,
        user_id=user_id,
    )

    shift_rows_by_id = {norm_str(item.get("shift_id")): item for item in shift_rows}
    deal_rows_by_id = {norm_str(item.get("deal_id")): item for item in deal_rows}

    preliminary_object_ids = unique_preserve_order(
        [norm_str(item.get("object_id")) for item in shift_rows + deal_rows]
    )
    object_rows = fetch_object_rows_by_ids(
        objects_pool=objects_pool,
        objects_database=objects_database,
        firm_id=firm_id,
        object_ids=preliminary_object_ids,
    )
    object_rows_by_id = {
        norm_str(item.get("object_id")): item for item in object_rows
    }

    normalized_events = _normalize_target_user_events(
        event_rows=event_rows,
        states_by_event_id=states_by_event_id,
        shift_histories=shift_histories,
        deal_histories=deal_histories,
        shift_rows_by_id=shift_rows_by_id,
        deal_rows_by_id=deal_rows_by_id,
        object_rows_by_id=object_rows_by_id,
        user_id=user_id,
        logger=logger,
    )

    all_object_ids = unique_preserve_order(
        preliminary_object_ids
        + [norm_str(item.get("object_id")) for item in normalized_events]
    )
    if set(all_object_ids) != set(preliminary_object_ids):
        object_rows = fetch_object_rows_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_id,
            object_ids=all_object_ids,
        )
        object_rows_by_id = {
            norm_str(item.get("object_id")): item for item in object_rows
        }
        normalized_events = _normalize_target_user_events(
            event_rows=event_rows,
            states_by_event_id=states_by_event_id,
            shift_histories=shift_histories,
            deal_histories=deal_histories,
            shift_rows_by_id=shift_rows_by_id,
            deal_rows_by_id=deal_rows_by_id,
            object_rows_by_id=object_rows_by_id,
            user_id=user_id,
            logger=logger,
        )
        all_object_ids = unique_preserve_order(
            preliminary_object_ids
            + [norm_str(item.get("object_id")) for item in normalized_events]
        )

    actual_intervals = _build_shift_actual_intervals(
        normalized_events=normalized_events,
        window_start=window_start,
        window_end=window_end,
        logger=logger,
    )
    actual_intervals.extend(
        _build_presence_intervals_from_events(
            normalized_events=normalized_events,
            window_start=window_start,
            window_end=window_end,
            logger=logger,
        )
    )

    planned_intervals = _build_shift_planned_intervals(
        shift_rows=shift_rows,
        window_start=window_start,
        window_end=window_end,
    )
    planned_intervals.extend(
        _build_deal_planned_intervals(
            deal_rows=deal_rows,
            normalized_events=normalized_events,
            window_start=window_start,
            window_end=window_end,
        )
    )

    totals = _aggregate_totals(
        actual_intervals=actual_intervals,
        planned_intervals=planned_intervals,
        window_start=window_start,
        window_end=window_end,
    )

    object_options = []
    for object_id in all_object_ids:
        object_row = object_rows_by_id.get(object_id, {})
        object_options.append(
            {
                "object_id": object_id,
                "object_name": norm_str(object_row.get("object_name")),
                "status": norm_str(object_row.get("status")),
                "address_json": object_row.get("address_json"),
            }
        )

    logger.info(
        "analytics_getter.employee_attendance.dataset_built",
        firm_id=firm_id,
        user_id=user_id,
        shift_rows_count=len(shift_rows),
        deal_rows_count=len(deal_rows),
        event_rows_count=len(event_rows),
        normalized_events_count=len(normalized_events),
        actual_intervals_count=len(actual_intervals),
        actual_merged_intervals_count=len(_merge_intervals(actual_intervals)),
        planned_intervals_count=len(planned_intervals),
        planned_merged_intervals_count=len(_merge_intervals(planned_intervals)),
        object_options_count=len(object_options),
    )

    return {
        "object_options": object_options,
        "object_rows_by_id": object_rows_by_id,
        "shift_rows": shift_rows,
        "deal_rows": deal_rows,
        "events": normalized_events,
        "actual_intervals": actual_intervals,
        "planned_intervals": planned_intervals,
        "totals": totals,
        "calendar_days": _calendar_days_payload(
            breakdown_actual=totals["actual_breakdown"],
            breakdown_planned=totals["planned_breakdown"],
            window_start=window_start,
            window_end=window_end,
        ),
    }


def filter_dataset_by_object(
    dataset: Dict[str, Any],
    object_id: str,
    *,
    window_start: datetime,
    window_end: datetime,
) -> Dict[str, Any]:
    normalized_object_id = norm_str(object_id)
    if not normalized_object_id:
        return dataset

    filtered_events = [
        item
        for item in dataset.get("events", [])
        if norm_str(item.get("object_id")) == normalized_object_id
    ]
    filtered_actual = [
        item
        for item in dataset.get("actual_intervals", [])
        if norm_str(item.get("object_id")) == normalized_object_id
    ]
    filtered_planned = [
        item
        for item in dataset.get("planned_intervals", [])
        if norm_str(item.get("object_id")) == normalized_object_id
    ]
    totals = _aggregate_totals(
        actual_intervals=filtered_actual,
        planned_intervals=filtered_planned,
        window_start=window_start,
        window_end=window_end,
    )
    return {
        **dataset,
        "selected_object_id": normalized_object_id,
        "events": filtered_events,
        "actual_intervals": filtered_actual,
        "planned_intervals": filtered_planned,
        "totals": totals,
        "calendar_days": _calendar_days_payload(
            breakdown_actual=totals["actual_breakdown"],
            breakdown_planned=totals["planned_breakdown"],
            window_start=window_start,
            window_end=window_end,
        ),
    }


def serialize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event_id": norm_str(event.get("event_id")),
        "event_type": norm_str(event.get("event_type")),
        "label": norm_str(event.get("label")),
        "event_at": to_iso_utc(event.get("event_at")),
        "object_id": norm_str(event.get("object_id")) or None,
        "object_name": norm_str(event.get("object_name")) or None,
        "shift_id": norm_str(event.get("shift_id")) or None,
        "shift_name": norm_str(event.get("shift_name")) or None,
        "deal_id": norm_str(event.get("deal_id")) or None,
        "deal_name": norm_str(event.get("deal_name")) or None,
    }
