# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from utils import bad_request, ok_response, server_error

from event_state import fetch_firm_event_states
from handlers_employee_finance import (
    _calc_totals,
    _collect_employee_events,
    _norm_text,
    _read_dispatcher_percent,
    _read_finance_event_rows,
    _safe_int,
    _year_range,
)


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

