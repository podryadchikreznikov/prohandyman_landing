# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from utils import bad_request, ok_response, server_error

from event_state import fetch_firm_event_states
from handlers_employee_finance import (
    _build_current_finance_snapshot,
    _build_month_preview,
    _build_response_events,
    _calc_totals,
    _collect_employee_events,
    _month_range,
    _norm_text,
    _parse_month_year,
    _parse_page,
    _read_dispatcher_attribution,
    _read_employee_salary_snapshot,
    _read_finance_event_rows,
    _read_fine_disputes_by_event_ids,
    _read_objects_by_ids,
    _resolve_period_as_of,
)


def handle_employee_finance_month_list(
    body,
    firm_id,
    events_pool,
    events_database,
    notices_pool,
    notices_database,
    objects_pool,
    objects_database,
    appeals_pool,
    appeals_database,
    firms_pool,
    firms_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_finance_month_list.start", firm_id=firm_id)

    user_id = _norm_text(body.get("user_id"))
    if not user_id:
        return bad_request("user_id is required")

    month, year, period_error = _parse_month_year(body)
    if period_error:
        return bad_request(period_error)

    page, page_size, page_error = _parse_page(body)
    if page_error:
        return bad_request(page_error)

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

        total = len(employee_month_events)
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, total)
        page_items = employee_month_events[start_idx:end_idx] if start_idx < total else []

        object_ids = [
            _norm_text(item.get("object_id"))
            for item in page_items
            if _norm_text(item.get("object_id"))
        ]
        objects_map = _read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_id,
            object_ids=object_ids,
        )
        fine_event_ids = [
            _norm_text(item.get("event_id"))
            for item in page_items
            if _norm_text(item.get("event_type_upper")) == "FINE"
            and _norm_text(item.get("event_id"))
        ]
        fine_disputes_by_event_id = _read_fine_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_id,
            event_ids=fine_event_ids,
        )

        response_events = _build_response_events(
            events=page_items,
            objects_map=objects_map,
            fine_disputes_by_event_id=fine_disputes_by_event_id,
        )
        dispatcher_percent = dispatcher_attribution.get("percent_snapshot", 0.0)

        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        has_prev = page > 0 and total > 0
        has_next = end_idx < total

        logger.info(
            "analytics_getter.employee_finance_month_list.success",
            firm_id=firm_id,
            user_id=user_id,
            month=month,
            year=year,
            total=total,
            page=page,
            page_size=page_size,
            page_items=len(response_events),
            month_pending_kopeks=month_totals["pending_kopeks"],
            current_pending_kopeks=current_snapshot["amount_kopeks"],
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev,
                "events_count": total,
                "dispatcher_percent": dispatcher_percent,
                "total_paid_kopeks": month_totals["paid_kopeks"],
                "total_pending_kopeks": current_snapshot["amount_kopeks"],
                "month_preview": _build_month_preview(current_snapshot),
                "finance_events": response_events,
            }
        )
    except Exception as e:
        logger.error("analytics_getter.employee_finance_month_list.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_month_list.error", error=str(e))
        return server_error("Internal Server Error")

