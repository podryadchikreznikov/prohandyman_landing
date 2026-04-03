# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from typing import Any, Dict

from event_state import fetch_firm_event_states
from utils import bad_request, ok_response

from .queries import (
    build_latest_assign_maps,
    build_latest_manual_presence_by_user,
    fetch_assign_event_rows,
    fetch_manual_presence_rows,
    fetch_object_deals_for_day,
    fetch_object_employee_rows,
    fetch_object_shifts_for_day,
    fetch_user_profiles_map,
    fetch_worker_percents_map,
)
from .resolver import resolve_object_presence_worker
from .shared import (
    extract_profile_role_label,
    norm_ids,
    norm_str,
    parse_date_utc,
    role_label_from_role_type,
    to_iso_utc,
)


def handle_object_activity_presence(
    *,
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
    logger.info("analytics_getter.object_activity_presence.start", firm_id=firm_id)

    object_id = str(body.get("object_id") or "").strip()
    date_str = norm_str(body.get("date"))
    if not object_id:
        logger.warn("analytics_getter.object_activity_presence.missing_object_id")
        return bad_request("object_id is required")
    if not date_str:
        logger.warn("analytics_getter.object_activity_presence.missing_date")
        return bad_request("date is required (YYYY-MM-DD)")

    try:
        start_at, end_at = parse_date_utc(date_str)
    except Exception:
        logger.warn(
            "analytics_getter.object_activity_presence.invalid_date", date=date_str
        )
        return bad_request("Invalid date format. Use YYYY-MM-DD")

    try:
        employee_rows = fetch_object_employee_rows(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            object_id=object_id,
        )
        employee_rows = [
            row
            for row in employee_rows
            if norm_str(row.get("role_type")).lower() in {"worker", "foreman"}
        ]
        employee_rows_by_user_id: Dict[str, Dict[str, Any]] = {}
        for row in employee_rows:
            user_id = norm_str(row.get("user_id"))
            if not user_id:
                continue
            employee_rows_by_user_id[user_id] = row

        shift_rows = fetch_object_shifts_for_day(
            objects_pool=objects_pool,
            objects_database=objects_database,
            object_id=object_id,
            start_at=start_at,
            end_at=end_at,
        )
        deal_rows = fetch_object_deals_for_day(
            objects_pool=objects_pool,
            objects_database=objects_database,
            object_id=object_id,
            start_at=start_at,
            end_at=end_at,
        )

        shift_ids = [row.get("shift_id") for row in shift_rows if row.get("shift_id")]
        deal_ids = [row.get("deal_id") for row in deal_rows if row.get("deal_id")]

        assign_event_rows = fetch_assign_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            end_at=end_at,
        )

        assign_event_ids = [
            row.get("event_id")
            for row in assign_event_rows
            if isinstance(row, dict) and row.get("event_id")
        ]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=assign_event_ids,
            logger=logger,
        )

        latest_shift_assign_by_id, latest_deal_assign_by_id = build_latest_assign_maps(
            assign_event_rows=assign_event_rows,
            states_by_event_id=states_by_event_id,
            shift_ids=shift_ids,
            deal_ids=deal_ids,
        )

        shifts_by_user: Dict[str, list] = {}
        for shift in shift_rows:
            shift_id = norm_str(shift.get("shift_id"))
            if not shift_id:
                continue
            assign_state = latest_shift_assign_by_id.get(shift_id)
            worker_id = norm_str((assign_state or {}).get("worker_id"))
            if not worker_id:
                continue
            shifts_by_user.setdefault(worker_id, []).append(
                {
                    **shift,
                    "assign_event_id": norm_str((assign_state or {}).get("event_id")),
                    "assign_event_at": norm_str((assign_state or {}).get("event_at")),
                }
            )

        deals_by_user: Dict[str, list] = {}
        for deal in deal_rows:
            deal_id = norm_str(deal.get("deal_id"))
            if not deal_id:
                continue
            assign_state = latest_deal_assign_by_id.get(deal_id)
            worker_id = norm_str((assign_state or {}).get("worker_id"))
            if not worker_id:
                continue
            deals_by_user.setdefault(worker_id, []).append(
                {
                    **deal,
                    "assign_event_id": norm_str((assign_state or {}).get("event_id")),
                    "assign_event_at": norm_str((assign_state or {}).get("event_at")),
                }
            )

        candidate_user_ids = norm_ids(
            list(employee_rows_by_user_id.keys())
            + list(shifts_by_user.keys())
            + list(deals_by_user.keys())
        )
        manual_presence_rows = fetch_manual_presence_rows(
            events_pool=events_pool,
            events_database=events_database,
            user_ids=candidate_user_ids,
            start_at=start_at,
            end_at=end_at,
        )
        manual_presence_event_ids = [
            row.get("event_id")
            for row in manual_presence_rows
            if isinstance(row, dict) and row.get("event_id")
        ]
        if manual_presence_event_ids:
            states_by_event_id.update(
                fetch_firm_event_states(
                    meta_pool=meta_pool,
                    meta_database=meta_database,
                    firm_id=firm_id,
                    event_ids=manual_presence_event_ids,
                    logger=logger,
                )
            )
        latest_manual_presence_by_user = build_latest_manual_presence_by_user(
            manual_presence_rows=manual_presence_rows,
            states_by_event_id=states_by_event_id,
            firm_id=firm_id,
            object_id=object_id,
        )
        candidate_user_ids = norm_ids(
            candidate_user_ids + list(latest_manual_presence_by_user.keys())
        )

        profiles_by_id = fetch_user_profiles_map(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_ids=candidate_user_ids,
        )
        worker_percents = fetch_worker_percents_map(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
        )

        now_utc = datetime.now(timezone.utc)
        selected_date_is_today = start_at <= now_utc < end_at
        evaluation_at = now_utc if selected_date_is_today else end_at

        workers = []
        for user_id in candidate_user_ids:
            row = employee_rows_by_user_id.get(user_id) or {}
            role_type = norm_str(row.get("role_type")).lower()
            if not role_type and (user_id in shifts_by_user or user_id in deals_by_user):
                role_type = "worker"
            profile = profiles_by_id.get(user_id)
            resolved = resolve_object_presence_worker(
                role_type=role_type,
                shifts=shifts_by_user.get(user_id, []),
                deals=deals_by_user.get(user_id, []),
                latest_manual_presence=latest_manual_presence_by_user.get(user_id),
                evaluation_at=evaluation_at,
                selected_date_is_today=selected_date_is_today,
            ) or {}
            workers.append(
                {
                    "user_id": user_id,
                    "status": norm_str(resolved.get("status")) or "absent",
                    "is_present": bool(resolved.get("is_present")),
                    "last_event_type": norm_str(resolved.get("event_type")) or None,
                    "last_event_id": norm_str(resolved.get("event_id")) or None,
                    "last_event_at": to_iso_utc(resolved.get("event_at")),
                    "user_profile": profile,
                    "role_label": extract_profile_role_label(profile)
                    or role_label_from_role_type(role_type),
                    "dispatcher_percent": worker_percents.get(user_id),
                }
            )

        workers.sort(
            key=lambda item: (
                0 if item.get("is_present") else 1,
                str(((item.get("user_profile") or {}).get("full_name") or "")).lower(),
                str(item.get("user_id") or ""),
            )
        )

        workers_present = sum(1 for worker in workers if worker.get("is_present"))
        total_workers = len(workers)

        logger.info(
            "analytics_getter.object_activity_presence.success",
            object_id=object_id,
            date=date_str,
            employee_rows=len(employee_rows),
            candidate_user_ids=len(candidate_user_ids),
            shift_rows=len(shift_rows),
            deal_rows=len(deal_rows),
            assign_event_rows=len(assign_event_rows),
            manual_presence_rows=len(manual_presence_rows),
            workers_present=workers_present,
            total_workers=total_workers,
        )

        return ok_response(
            {
                "object_id": object_id,
                "workers_present": workers_present,
                "total_workers": total_workers,
                "updated_at": to_iso_utc(datetime.now(timezone.utc)),
                "workers": workers,
            }
        )
    except Exception as exc:
        logger.error("analytics_getter.object_activity_presence.error", error=str(exc))
        hlog.exception("analytics_getter.object_activity_presence.error", error=str(exc))
        from utils import server_error

        return server_error("Internal Server Error")
