# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from utils import ok_response, bad_request
from common import safe_json


def handle_employee_calendar_day_period(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_calendar_day_period.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    date_str = body.get("date")
    
    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_calendar_day_period.missing_params")
        return bad_request("user_id and date are required")
    
    try:
        target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        next_date = target_date + timedelta(days=1)
    except ValueError as e:
        logger.warn("analytics_getter.employee_calendar_day_period.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")
    
    try:
        query_calendar = f"""
        SELECT event_id, event_type, created_at, metadata_json
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('SHIFT_END', 'DEAL_COMPLETE', 'DEAL_ASSIGN', 'SHIFT_ASSIGN', 
                             'SHIFT_FORCE_END', 'ABSENCE', 'SHIFT_START', 'SHIFT_REFUSE', 
                             'SHIFT_CANCEL', 'DEAL_REFUSE', 'DEAL_CANCEL', 'OBJ_ATTACH', 
                             'OBJ_DETACH', 'OBJ_ENTER', 'OBJ_LEAVE')
          AND created_at >= CAST('{target_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{next_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_calendar, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        period_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                metadata = safe_json(row.metadata_json) if hasattr(row, 'metadata_json') and row.metadata_json else {}
                event_user_id = metadata.get("user_id") or metadata.get("employee_id")
                if event_user_id == user_id:
                    period_events.append({
                        "event_id": row.event_id,
                        "event_type": row.event_type,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "metadata": metadata,
                    })
        
        logger.info("analytics_getter.employee_calendar_day_period.success", user_id=user_id, date=date_str, events_count=len(period_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "date": date_str,
            "period_events": period_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_calendar_day_period.error", error=str(e))
        hlog.exception("analytics_getter.employee_calendar_day_period.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_calendar_day_upcoming(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_calendar_day_upcoming.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    date_str = body.get("date")
    
    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_calendar_day_upcoming.missing_params")
        return bad_request("user_id and date are required")
    
    try:
        target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        next_date = target_date + timedelta(days=1)
    except ValueError as e:
        logger.warn("analytics_getter.employee_calendar_day_upcoming.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")
    
    try:
        query_upcoming = f"""
        SELECT event_id, event_type, created_at, metadata_json
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('DEAL_ASSIGN', 'SHIFT_ASSIGN')
          AND created_at >= CAST('{target_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{next_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_upcoming, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        upcoming_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                metadata = safe_json(row.metadata_json) if hasattr(row, 'metadata_json') and row.metadata_json else {}
                event_user_id = metadata.get("user_id") or metadata.get("employee_id")
                if event_user_id == user_id:
                    upcoming_events.append({
                        "event_id": row.event_id,
                        "event_type": row.event_type,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                        "metadata": metadata,
                    })
        
        logger.info("analytics_getter.employee_calendar_day_upcoming.success", user_id=user_id, date=date_str, events_count=len(upcoming_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "date": date_str,
            "upcoming_events": upcoming_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_calendar_day_upcoming.error", error=str(e))
        hlog.exception("analytics_getter.employee_calendar_day_upcoming.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")