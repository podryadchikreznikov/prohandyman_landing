# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from utils import bad_request, ok_response, server_error

from common import safe_json


def handle_employee_time_days_month(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_days_month.start", firm_id=firm_id)

    user_id = body.get("user_id")
    month = body.get("month")
    year = body.get("year")

    if not user_id or not month or not year:
        logger.warn("analytics_getter.employee_time_days_month.missing_params")
        return bad_request("user_id, month, and year are required")

    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_days_month.invalid_date", error=str(e))
        return bad_request("Invalid month or year")

    try:
        query_time_events = f"""
        SELECT event_id, event_type, created_at, metadata_json
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('OBJ_ENTER', 'OBJ_LEAVE', 'SHIFT_END', 'DEAL_COMPLETE')
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """

        events_result = None

        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_time_events, commit_tx=True)

        events_pool.retry_operation_sync(_read_events)

        days_breakdown = {}
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                metadata = safe_json(row.metadata_json) if hasattr(row, "metadata_json") and row.metadata_json else {}
                event_user_id = metadata.get("user_id") or metadata.get("employee_id")
                if event_user_id == user_id and row.created_at:
                    day_key = row.created_at.date().isoformat()
                    if day_key not in days_breakdown:
                        days_breakdown[day_key] = []
                    days_breakdown[day_key].append(
                        {
                            "event_id": row.event_id,
                            "event_type": row.event_type,
                            "created_at": row.created_at.isoformat(),
                        }
                    )

        logger.info("analytics_getter.employee_time_days_month.success", user_id=user_id, days_count=len(days_breakdown))

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "days_breakdown": days_breakdown,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_time_days_month.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_days_month.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_time_days_month_object(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_days_month_object.start", firm_id=firm_id)

    user_id = body.get("user_id")
    object_id = body.get("object_id")
    month = body.get("month")
    year = body.get("year")

    if not user_id or not object_id or not month or not year:
        logger.warn("analytics_getter.employee_time_days_month_object.missing_params")
        return bad_request("user_id, object_id, month, and year are required")

    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_days_month_object.invalid_date", error=str(e))
        return bad_request("Invalid month or year")

    try:
        query_time_events = f"""
        SELECT event_id, event_type, created_at, metadata_json
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('OBJ_ENTER', 'OBJ_LEAVE', 'SHIFT_END', 'DEAL_COMPLETE')
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """

        events_result = None

        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_time_events, commit_tx=True)

        events_pool.retry_operation_sync(_read_events)

        days_breakdown = {}
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                metadata = safe_json(row.metadata_json) if hasattr(row, "metadata_json") and row.metadata_json else {}
                event_user_id = metadata.get("user_id") or metadata.get("employee_id")
                event_object_id = metadata.get("object_id")
                if event_user_id == user_id and event_object_id == object_id and row.created_at:
                    day_key = row.created_at.date().isoformat()
                    if day_key not in days_breakdown:
                        days_breakdown[day_key] = []
                    days_breakdown[day_key].append(
                        {
                            "event_id": row.event_id,
                            "event_type": row.event_type,
                            "created_at": row.created_at.isoformat(),
                        }
                    )

        logger.info(
            "analytics_getter.employee_time_days_month_object.success",
            user_id=user_id,
            object_id=object_id,
            days_count=len(days_breakdown),
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "object_id": object_id,
                "month": month,
                "year": year,
                "days_breakdown": days_breakdown,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_time_days_month_object.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_days_month_object.error", error=str(e))
        return server_error("Internal Server Error")

