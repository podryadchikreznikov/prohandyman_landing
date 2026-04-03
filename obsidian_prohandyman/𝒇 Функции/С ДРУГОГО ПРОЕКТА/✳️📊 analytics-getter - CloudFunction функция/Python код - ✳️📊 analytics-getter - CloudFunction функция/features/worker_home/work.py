# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List

import ydb

from utils import bad_request, forbidden, ok_response

from event_state import extract_user_id, fetch_firm_event_states
from handlers_worker_home import (
    _collect_worker_assignments_for_firm,
    _day_range,
    _month_range,
    _read_event_ids,
    _read_worker_memberships_all_firms,
)


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

