# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from utils import bad_request, ok_response, server_error

from event_state import fetch_firm_event_states
from handlers_employee_finance import (
    _build_current_finance_snapshot,
    _calc_totals,
    _collect_employee_events,
    _month_range,
    _norm_text,
    _parse_month_year,
    _read_dispatcher_attribution,
    _read_employee_salary_snapshot,
    _read_finance_event_rows,
    _resolve_period_as_of,
)


def handle_employee_finance_month_total(
    body,
    firm_id,
    events_pool,
    events_database,
    notices_pool,
    notices_database,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_finance_month_total.start", firm_id=firm_id)

    user_id = _norm_text(body.get("user_id"))
    if not user_id:
        return bad_request("user_id is required")

    month, year, period_error = _parse_month_year(body)
    if period_error:
        return bad_request(period_error)

    try:
        start, end = _month_range(year=year, month=month)
        month_event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start,
            end=end,
        )
        snapshot_as_of = _resolve_period_as_of(end)
        snapshot_event_rows = _read_finance_event_rows(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            end=snapshot_as_of + timedelta(seconds=1),
        )

        event_ids = [
            row["event_id"]
            for row in [*month_event_rows, *snapshot_event_rows]
            if _norm_text(row.get("event_id"))
        ]
        states_by_event_id = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )

        employee_month_events = _collect_employee_events(
            event_rows=month_event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        employee_snapshot_events = _collect_employee_events(
            event_rows=snapshot_event_rows,
            states_by_event_id=states_by_event_id,
            user_id=user_id,
        )
        month_totals = _calc_totals(employee_month_events)
        salary_snapshot = _read_employee_salary_snapshot(
            notices_pool=notices_pool,
            notices_database=notices_database,
            firm_id=firm_id,
            user_id=user_id,
            as_of=snapshot_as_of,
        )
        dispatcher_attribution = _read_dispatcher_attribution(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
            user_id=user_id,
        )
        current_snapshot = _build_current_finance_snapshot(
            firm_id=firm_id,
            user_id=user_id,
            user_name=None,
            role_type=None,
            all_events=employee_snapshot_events,
            salary_snapshot=salary_snapshot,
            dispatcher_attribution=dispatcher_attribution,
            as_of=snapshot_as_of,
        )
        dispatcher_percent = dispatcher_attribution.get("percent_snapshot", 0.0)

        logger.info(
            "analytics_getter.employee_finance_month_total.success",
            firm_id=firm_id,
            user_id=user_id,
            month=month,
            year=year,
            events_count=len(employee_month_events),
            paid_kopeks=month_totals["paid_kopeks"],
            month_pending_kopeks=month_totals["pending_kopeks"],
            current_pending_kopeks=current_snapshot["amount_kopeks"],
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "events_count": len(employee_month_events),
                "events_with_amount_count": month_totals["events_with_amount_count"],
                "dispatcher_percent": dispatcher_percent,
                "total_paid_kopeks": month_totals["paid_kopeks"],
                "total_pending_kopeks": current_snapshot["amount_kopeks"],
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_month_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_month_total.error", error=str(e))
        return server_error("Internal Server Error")

