# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone

from utils import bad_request, ok_response, server_error

from common import safe_json


def handle_employee_time_day_timeline(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_day_timeline.start", firm_id=firm_id)

    user_id = body.get("user_id")
    date_str = body.get("date")

    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_time_day_timeline.missing_params")
        return bad_request("user_id and date are required (YYYY-MM-DD)")

    try:
        target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        next_date = target_date + timedelta(days=1)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_day_timeline.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")

    try:
        query_timeline = f"""
        SELECT event_id, event_type, created_at, metadata_json
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('OBJ_ENTER', 'OBJ_LEAVE', 'SHIFT_END', 'DEAL_COMPLETE')
          AND created_at >= CAST('{target_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{next_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """

        events_result = None

        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_timeline, commit_tx=True)

        events_pool.retry_operation_sync(_read_events)

        timeline_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                metadata = safe_json(row.metadata_json) if hasattr(row, "metadata_json") and row.metadata_json else {}
                event_user_id = metadata.get("user_id") or metadata.get("employee_id")
                if event_user_id == user_id:
                    timeline_events.append(
                        {
                            "event_id": row.event_id,
                            "event_type": row.event_type,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                        }
                    )

        logger.info(
            "analytics_getter.employee_time_day_timeline.success",
            user_id=user_id,
            date=date_str,
            events_count=len(timeline_events),
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "date": date_str,
                "timeline_events": timeline_events,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_time_day_timeline.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_day_timeline.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_time_day_object_timeline(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_day_object_timeline.start", firm_id=firm_id)

    user_id = body.get("user_id")
    object_id = body.get("object_id")
    date_str = body.get("date")

    if not user_id or not object_id or not date_str:
        logger.warn("analytics_getter.employee_time_day_object_timeline.missing_params")
        return bad_request("user_id, object_id, and date are required")

    try:
        target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        next_date = target_date + timedelta(days=1)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_day_object_timeline.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")

    try:
        query_timeline = f"""
        SELECT event_id, event_type, created_at, metadata_json
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('OBJ_ENTER', 'OBJ_LEAVE', 'SHIFT_END', 'DEAL_COMPLETE')
          AND created_at >= CAST('{target_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{next_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """

        events_result = None

        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_timeline, commit_tx=True)

        events_pool.retry_operation_sync(_read_events)

        timeline_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                metadata = safe_json(row.metadata_json) if hasattr(row, "metadata_json") and row.metadata_json else {}
                event_user_id = metadata.get("user_id") or metadata.get("employee_id")
                event_object_id = metadata.get("object_id")
                if event_user_id == user_id and event_object_id == object_id:
                    timeline_events.append(
                        {
                            "event_id": row.event_id,
                            "event_type": row.event_type,
                            "created_at": row.created_at.isoformat() if row.created_at else None,
                        }
                    )

        logger.info(
            "analytics_getter.employee_time_day_object_timeline.success",
            user_id=user_id,
            object_id=object_id,
            events_count=len(timeline_events),
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "object_id": object_id,
                "date": date_str,
                "timeline_events": timeline_events,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_time_day_object_timeline.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_day_object_timeline.error", error=str(e))
        return server_error("Internal Server Error")

