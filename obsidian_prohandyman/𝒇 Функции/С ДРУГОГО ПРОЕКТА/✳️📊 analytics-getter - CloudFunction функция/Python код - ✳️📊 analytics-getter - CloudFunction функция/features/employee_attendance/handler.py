# -*- coding: utf-8 -*-
from __future__ import annotations

from utils import bad_request, ok_response, server_error

from .pipeline import (
    build_employee_attendance_dataset,
    filter_dataset_by_object,
    serialize_event,
)
from .shared import hours_from_seconds, norm_str, parse_day_window_utc, parse_month_window_utc


def handle_employee_attendance_month_summary(
    *,
    body,
    firm_id,
    objects_pool,
    objects_database,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_attendance_month_summary.start", firm_id=firm_id)

    user_id = norm_str(body.get("user_id"))
    object_id = norm_str(body.get("object_id"))
    month = body.get("month")
    year = body.get("year")

    if not user_id or month is None or year is None:
        logger.warn("analytics_getter.employee_attendance_month_summary.missing_params")
        return bad_request("user_id, month and year are required")

    try:
        month = int(month)
        year = int(year)
        window_start, window_end = parse_month_window_utc(year, month)
    except Exception as e:
        logger.warn(
            "analytics_getter.employee_attendance_month_summary.invalid_period",
            error=str(e),
        )
        return bad_request("Invalid month or year")

    try:
        dataset = build_employee_attendance_dataset(
            firm_id=firm_id,
            user_id=user_id,
            window_start=window_start,
            window_end=window_end,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        filtered = filter_dataset_by_object(
            dataset,
            object_id,
            window_start=window_start,
            window_end=window_end,
        )
        totals = filtered["totals"]
        response = {
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "selected_object_id": norm_str(filtered.get("selected_object_id")) or None,
            "period_started_at": window_start.isoformat().replace("+00:00", "Z"),
            "period_ended_at": window_end.isoformat().replace("+00:00", "Z"),
            "objects": filtered.get("object_options", []),
            "calendar_days": filtered.get("calendar_days", []),
            "totals": {
                "actual_seconds": totals["actual_seconds"],
                "actual_hours": totals["actual_hours"],
                "planned_seconds": totals["planned_seconds"],
                "planned_hours": totals["planned_hours"],
                "unique_objects_count": len(totals["actual_unique_object_ids"]),
            },
        }
        logger.info(
            "analytics_getter.employee_attendance_month_summary.success",
            user_id=user_id,
            month=month,
            year=year,
            selected_object_id=response["selected_object_id"],
            objects_count=len(response["objects"]),
            calendar_days_count=len(response["calendar_days"]),
        )
        return ok_response(response)
    except Exception as e:
        logger.error("analytics_getter.employee_attendance_month_summary.error", error=str(e))
        hlog.exception("analytics_getter.employee_attendance_month_summary.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_attendance_day_details(
    *,
    body,
    firm_id,
    objects_pool,
    objects_database,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_attendance_day_details.start", firm_id=firm_id)

    user_id = norm_str(body.get("user_id"))
    object_id = norm_str(body.get("object_id"))
    date_str = norm_str(body.get("date"))

    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_attendance_day_details.missing_params")
        return bad_request("user_id and date are required")

    try:
        window_start, window_end = parse_day_window_utc(date_str)
    except Exception as e:
        logger.warn(
            "analytics_getter.employee_attendance_day_details.invalid_date",
            error=str(e),
        )
        return bad_request("Invalid date format, expected YYYY-MM-DD")

    try:
        dataset = build_employee_attendance_dataset(
            firm_id=firm_id,
            user_id=user_id,
            window_start=window_start,
            window_end=window_end,
            objects_pool=objects_pool,
            objects_database=objects_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        filtered = filter_dataset_by_object(
            dataset,
            object_id,
            window_start=window_start,
            window_end=window_end,
        )
        totals = filtered["totals"]
        response = {
            "user_id": user_id,
            "firm_id": firm_id,
            "date": date_str,
            "selected_object_id": norm_str(filtered.get("selected_object_id")) or None,
            "events": [serialize_event(item) for item in filtered.get("events", [])],
            "totals": {
                "actual_seconds": totals["actual_seconds"],
                "actual_hours": totals["actual_hours"],
                "planned_seconds": totals["planned_seconds"],
                "planned_hours": totals["planned_hours"],
                "unique_objects_count": len(totals["actual_unique_object_ids"]),
            },
        }
        logger.info(
            "analytics_getter.employee_attendance_day_details.success",
            user_id=user_id,
            date=date_str,
            selected_object_id=response["selected_object_id"],
            events_count=len(response["events"]),
            actual_hours=hours_from_seconds(totals["actual_seconds"]),
        )
        return ok_response(response)
    except Exception as e:
        logger.error("analytics_getter.employee_attendance_day_details.error", error=str(e))
        hlog.exception("analytics_getter.employee_attendance_day_details.error", error=str(e))
        return server_error("Internal Server Error")
