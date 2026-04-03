# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import ydb

from utils import bad_request, ok_response

from constants import EVENT_TYPE_FINE
from event_state import extract_amount_kopeks, extract_user_id, fetch_firm_event_states
from handlers_worker_home import _month_range, _read_event_ids, _year_range


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

