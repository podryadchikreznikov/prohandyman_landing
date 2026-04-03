# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from constants import EVENT_TYPE_OBJ_ENTER, EVENT_TYPE_OBJ_LEAVE
from handlers_employee_finance import _coerce_datetime_utc

from .shared import candidate, norm_str, pick_latest_candidate


SHIFT_PRESENCE_TERMINAL_STATUSES = {
    "completed",
    "force_completed",
    "cancelled",
    "force_cancelled",
    "rejected",
}
DEAL_PRESENCE_TERMINAL_STATUSES = {
    "archived",
    "completed",
    "force_completed",
    "cancelled",
    "force_cancelled",
    "rejected",
}
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


def resolve_object_presence_worker(
    *,
    role_type: str,
    shifts: List[Dict[str, Any]],
    deals: List[Dict[str, Any]],
    latest_manual_presence: Optional[Dict[str, Any]],
    evaluation_at: datetime,
    selected_date_is_today: bool,
):
    candidates: List[Dict[str, Any]] = []
    is_foreman = "foreman" in role_type

    if is_foreman:
        if isinstance(latest_manual_presence, dict):
            event_type = norm_str(latest_manual_presence.get("event_type")).lower()
            if event_type == EVENT_TYPE_OBJ_ENTER:
                item = candidate(
                    event_type,
                    latest_manual_presence.get("event_at"),
                    status="present",
                    is_present=True,
                    event_id=norm_str(latest_manual_presence.get("event_id")) or None,
                )
                if item:
                    candidates.append(item)
            elif event_type == EVENT_TYPE_OBJ_LEAVE:
                item = candidate(
                    event_type,
                    latest_manual_presence.get("event_at"),
                    status="finished",
                    is_present=False,
                    event_id=norm_str(latest_manual_presence.get("event_id")) or None,
                )
                if item:
                    candidates.append(item)
        return pick_latest_candidate(candidates)

    for shift in shifts:
        status = norm_str(shift.get("status")).lower()
        opened_at = _coerce_datetime_utc(shift.get("opened_at"))
        deadline_at = _coerce_datetime_utc(shift.get("deadline_at"))
        closed_at = _coerce_datetime_utc(shift.get("closed_at"))
        updated_at = _coerce_datetime_utc(shift.get("updated_at"))
        created_at = _coerce_datetime_utc(shift.get("created_at"))
        assign_at = _coerce_datetime_utc(shift.get("assign_event_at"))

        if status in SHIFT_PRESENCE_TERMINAL_STATUSES:
            item = candidate(
                SHIFT_PRESENCE_TERMINAL_EVENT_BY_STATUS.get(status, "shift_end"),
                closed_at or updated_at or created_at,
                status="finished",
                is_present=False,
                event_id=norm_str(shift.get("terminal_event_id")) or None,
            )
            if item:
                candidates.append(item)
            continue

        if status == "active" and opened_at is not None:
            if selected_date_is_today and (
                deadline_at is None or evaluation_at <= deadline_at
            ):
                item = candidate(
                    "shift_start",
                    opened_at,
                    status="present",
                    is_present=True,
                    event_id=norm_str(shift.get("start_event_id")) or None,
                )
            else:
                item = candidate(
                    "shift_start",
                    opened_at,
                    status="absent",
                    is_present=False,
                    event_id=norm_str(shift.get("start_event_id")) or None,
                )
            if item:
                candidates.append(item)
            continue

        item = candidate(
            "shift_assign",
            assign_at or _coerce_datetime_utc(shift.get("start_at")) or created_at,
            status="absent",
            is_present=False,
            event_id=norm_str(shift.get("assign_event_id")) or None,
        )
        if item:
            candidates.append(item)

    for deal in deals:
        status = norm_str(deal.get("status")).lower()
        deadline_at = _coerce_datetime_utc(deal.get("deadline_at"))
        start_at = _coerce_datetime_utc(deal.get("start_at"))
        updated_at = _coerce_datetime_utc(deal.get("updated_at"))
        created_at = _coerce_datetime_utc(deal.get("created_at"))
        assign_at = _coerce_datetime_utc(deal.get("assign_event_at"))

        if status in DEAL_PRESENCE_TERMINAL_STATUSES:
            item = candidate(
                DEAL_PRESENCE_TERMINAL_EVENT_BY_STATUS.get(status, "deal_complete"),
                updated_at or created_at,
                status="finished",
                is_present=False,
                event_id=norm_str(deal.get("terminal_event_id")) or None,
            )
            if item:
                candidates.append(item)
            continue

        deal_is_started = start_at is None or evaluation_at >= start_at
        deal_is_not_overdue = deadline_at is None or evaluation_at <= deadline_at
        if status == "active" and selected_date_is_today and deal_is_started and deal_is_not_overdue:
            item = candidate(
                "deal_assign",
                start_at or assign_at or created_at,
                status="present",
                is_present=True,
                event_id=norm_str(deal.get("assign_event_id")) or None,
            )
            if item:
                candidates.append(item)
            continue

        if status == "active":
            item = candidate(
                "deal_assign",
                start_at or assign_at or created_at,
                status="absent",
                is_present=False,
                event_id=norm_str(deal.get("assign_event_id")) or None,
            )
            if item:
                candidates.append(item)
            continue

        item = candidate(
            "deal_assign",
            assign_at or start_at or created_at,
            status="absent",
            is_present=False,
            event_id=norm_str(deal.get("assign_event_id")) or None,
        )
        if item:
            candidates.append(item)

    if isinstance(latest_manual_presence, dict):
        event_type = norm_str(latest_manual_presence.get("event_type")).lower()
        if event_type == EVENT_TYPE_OBJ_LEAVE:
            item = candidate(
                event_type,
                latest_manual_presence.get("event_at"),
                status="finished",
                is_present=False,
                event_id=norm_str(latest_manual_presence.get("event_id")) or None,
            )
            if item:
                candidates.append(item)

    return pick_latest_candidate(candidates)
