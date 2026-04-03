# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from utils import ok_response, bad_request
from common import safe_json


def handle_employee_absences_total(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_total.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    if not user_id:
        logger.warn("analytics_getter.employee_absences_total.missing_user_id")
        return bad_request("user_id is required")
    
    try:
        query_absences = f"""
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = '{firm_id}' AND event_type = 'ABSENCE'
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_absences, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        total_absences = 0
        if events_result and events_result[0].rows:
            total_absences = len(list(events_result[0].rows))
        
        logger.info("analytics_getter.employee_absences_total.success", user_id=user_id, total=total_absences)
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "total_absences": total_absences,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_absences_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_total.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_absences_disputed(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_disputed.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    if not user_id:
        logger.warn("analytics_getter.employee_absences_disputed.missing_user_id")
        return bad_request("user_id is required")
    
    try:
        query_absences = f"""
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = '{firm_id}' AND event_type = 'ABSENCE'
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_absences, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        total_absences = 0
        if events_result and events_result[0].rows:
            total_absences = len(list(events_result[0].rows))
        
        disputed_count = 0
        
        logger.info("analytics_getter.employee_absences_disputed.success", user_id=user_id, total=total_absences, disputed=disputed_count)
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "total_absences": total_absences,
            "disputed_absences": disputed_count,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_absences_disputed.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_disputed.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_absences_month(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_month.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    month = body.get("month")
    year = body.get("year")
    
    if not user_id or not month or not year:
        logger.warn("analytics_getter.employee_absences_month.missing_params")
        return bad_request("user_id, month, and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_absences_month.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    try:
        query_absences = f"""
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = '{firm_id}' 
          AND event_type = 'ABSENCE'
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_absences, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        monthly_absences = 0
        if events_result and events_result[0].rows:
            monthly_absences = len(list(events_result[0].rows))
        
        logger.info("analytics_getter.employee_absences_month.success", user_id=user_id, month=month, year=year, total=monthly_absences)
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "monthly_absences": monthly_absences,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_absences_month.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_month.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_absences_month_details(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_month_details.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    month = body.get("month")
    year = body.get("year")
    
    if not user_id or not month or not year:
        logger.warn("analytics_getter.employee_absences_month_details.missing_params")
        return bad_request("user_id, month, and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_absences_month_details.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    try:
        query_absences = f"""
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = '{firm_id}' 
          AND event_type = 'ABSENCE'
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_absences, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        absence_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                absence_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        logger.info("analytics_getter.employee_absences_month_details.success", user_id=user_id, count=len(absence_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "absence_events": absence_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_absences_month_details.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_month_details.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_time_total(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_total.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    if not user_id:
        logger.warn("analytics_getter.employee_time_total.missing_user_id")
        return bad_request("user_id is required")
    
    try:
        query_time_events = f"""
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('OBJ_ENTER', 'OBJ_LEAVE', 'SHIFT_END', 'DEAL_COMPLETE')
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_time_events, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        total_time_seconds = 0
        time_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                time_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        logger.info("analytics_getter.employee_time_total.success", user_id=user_id, events_count=len(time_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "total_time_seconds": total_time_seconds,
            "time_events": time_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_total.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_time_month(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_month.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    month = body.get("month")
    year = body.get("year")
    
    if not user_id or not month or not year:
        logger.warn("analytics_getter.employee_time_month.missing_params")
        return bad_request("user_id, month, and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_month.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    try:
        query_time_events = f"""
        SELECT event_id, event_type, created_at
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
        
        total_time_seconds = 0
        time_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                time_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        logger.info("analytics_getter.employee_time_month.success", user_id=user_id, events_count=len(time_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "total_time_seconds": total_time_seconds,
            "time_events": time_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_month.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_month.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_time_month_object(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_month_object.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    object_id = body.get("object_id")
    month = body.get("month")
    year = body.get("year")
    
    if not user_id or not object_id or not month or not year:
        logger.warn("analytics_getter.employee_time_month_object.missing_params")
        return bad_request("user_id, object_id, month, and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_month_object.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    try:
        query_time_events = f"""
        SELECT event_id, event_type, created_at
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
        
        total_time_seconds = 0
        time_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                time_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        logger.info("analytics_getter.employee_time_month_object.success", user_id=user_id, object_id=object_id, events_count=len(time_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "object_id": object_id,
            "month": month,
            "year": year,
            "total_time_seconds": total_time_seconds,
            "time_events": time_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_month_object.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_month_object.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


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
        SELECT event_id, event_type, created_at
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
                if row.created_at:
                    day_key = row.created_at.date().isoformat()
                    if day_key not in days_breakdown:
                        days_breakdown[day_key] = []
                    days_breakdown[day_key].append({
                        "event_id": row.event_id,
                        "event_type": row.event_type,
                        "created_at": row.created_at.isoformat(),
                    })
        
        logger.info("analytics_getter.employee_time_days_month.success", user_id=user_id, days_count=len(days_breakdown))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "days_breakdown": days_breakdown,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_days_month.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_days_month.error", error=str(e))
        from utils import server_error
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
        SELECT event_id, event_type, created_at
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
                if row.created_at:
                    day_key = row.created_at.date().isoformat()
                    if day_key not in days_breakdown:
                        days_breakdown[day_key] = []
                    days_breakdown[day_key].append({
                        "event_id": row.event_id,
                        "event_type": row.event_type,
                        "created_at": row.created_at.isoformat(),
                    })
        
        logger.info("analytics_getter.employee_time_days_month_object.success", user_id=user_id, object_id=object_id, days_count=len(days_breakdown))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "object_id": object_id,
            "month": month,
            "year": year,
            "days_breakdown": days_breakdown,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_days_month_object.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_days_month_object.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_time_day_timeline(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_time_day_timeline.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    date_str = body.get("date")
    
    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_time_day_timeline.missing_params")
        return bad_request("user_id and date are required (YYYY-MM-DD)")
    
    try:
        target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        next_date = datetime(target_date.year, target_date.month, target_date.day + 1 if target_date.day < 28 else 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_day_timeline.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")
    
    try:
        query_timeline = f"""
        SELECT event_id, event_type, created_at
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
                timeline_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        logger.info("analytics_getter.employee_time_day_timeline.success", user_id=user_id, date=date_str, events_count=len(timeline_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "date": date_str,
            "timeline_events": timeline_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_day_timeline.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_day_timeline.error", error=str(e))
        from utils import server_error
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
        next_date = datetime(target_date.year, target_date.month, target_date.day + 1 if target_date.day < 28 else 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_time_day_object_timeline.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")
    
    try:
        query_timeline = f"""
        SELECT event_id, event_type, created_at
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
                timeline_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        logger.info("analytics_getter.employee_time_day_object_timeline.success", user_id=user_id, object_id=object_id, events_count=len(timeline_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "object_id": object_id,
            "date": date_str,
            "timeline_events": timeline_events,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_time_day_object_timeline.error", error=str(e))
        hlog.exception("analytics_getter.employee_time_day_object_timeline.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_calendar_day_period(body, firm_id, events_pool, events_database, logger, hlog):
    logger.info("analytics_getter.employee_calendar_day_period.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    date_str = body.get("date")
    
    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_calendar_day_period.missing_params")
        return bad_request("user_id and date are required")
    
    try:
        target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        next_date = datetime(target_date.year, target_date.month, target_date.day + 1 if target_date.day < 28 else 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_calendar_day_period.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")
    
    try:
        query_calendar = f"""
        SELECT event_id, event_type, created_at
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
                period_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
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
        next_date = datetime(target_date.year, target_date.month, target_date.day + 1 if target_date.day < 28 else 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_calendar_day_upcoming.invalid_date", error=str(e))
        return bad_request("Invalid date format. Use YYYY-MM-DD")
    
    try:
        query_upcoming = f"""
        SELECT event_id, event_type, created_at
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
                upcoming_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
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


def handle_employee_finance_month_list(body, firm_id, events_pool, events_database, firms_pool, firms_database, logger, hlog):
    logger.info("analytics_getter.employee_finance_month_list.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    month = body.get("month")
    year = body.get("year")
    
    if not user_id or not month or not year:
        logger.warn("analytics_getter.employee_finance_month_list.missing_params")
        return bad_request("user_id, month, and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_finance_month_list.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    try:
        query_finance = f"""
        SELECT event_id, event_type, created_at
        FROM finance_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('REWARD', 'FINE', 'SHIFT_END', 'DEAL_COMPLETE', 
                             'WITHHELD_SHIFT', 'WITHHOLD_ACCRUAL', 'ACCRUAL_DEFERRED')
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_finance, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        finance_events = []
        if events_result and events_result[0].rows:
            for row in events_result[0].rows:
                finance_events.append({
                    "event_id": row.event_id,
                    "event_type": row.event_type,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                })
        
        query_attributions = f"""
        SELECT worker_user_id, dispatcher_id, percent_snapshot
        FROM dispatcher_attributions
        WHERE firm_id = '{firm_id}' AND worker_user_id = '{user_id}'
        ORDER BY
            CASE
                WHEN attribution_type = 'dispatcher' THEN 0
                WHEN attribution_type = 'nominal' THEN 1
                ELSE 2
            END ASC,
            updated_at DESC,
            created_at DESC
        LIMIT 1;
        """
        
        attributions_result = None
        def _read_attributions(session):
            nonlocal attributions_result
            attributions_result = session.transaction().execute(query_attributions, commit_tx=True)
        
        firms_pool.retry_operation_sync(_read_attributions)
        
        dispatcher_percent = 0.0
        if attributions_result and attributions_result[0].rows:
            row = list(attributions_result[0].rows)[0]
            dispatcher_percent = row.percent_snapshot
        
        logger.info("analytics_getter.employee_finance_month_list.success", user_id=user_id, events_count=len(finance_events))
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "finance_events": finance_events,
            "dispatcher_percent": dispatcher_percent,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_finance_month_list.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_month_list.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_finance_month_total(body, firm_id, events_pool, events_database, firms_pool, firms_database, logger, hlog):
    logger.info("analytics_getter.employee_finance_month_total.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    month = body.get("month")
    year = body.get("year")
    
    if not user_id or not month or not year:
        logger.warn("analytics_getter.employee_finance_month_total.missing_params")
        return bad_request("user_id, month, and year are required")
    
    try:
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_finance_month_total.invalid_date", error=str(e))
        return bad_request("Invalid month or year")
    
    try:
        query_finance = f"""
        SELECT event_id, event_type, created_at
        FROM finance_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('REWARD', 'FINE', 'SHIFT_END', 'DEAL_COMPLETE', 
                             'WITHHELD_SHIFT', 'WITHHOLD_ACCRUAL', 'ACCRUAL_DEFERRED')
          AND created_at >= CAST('{start_date.isoformat()}' AS Timestamp)
          AND created_at < CAST('{end_date.isoformat()}' AS Timestamp)
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_finance, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        total_paid = 0
        total_pending = 0
        events_count = 0
        if events_result and events_result[0].rows:
            events_count = len(list(events_result[0].rows))
        
        query_attributions = f"""
        SELECT worker_user_id, dispatcher_id, percent_snapshot
        FROM dispatcher_attributions
        WHERE firm_id = '{firm_id}' AND worker_user_id = '{user_id}'
        ORDER BY
            CASE
                WHEN attribution_type = 'dispatcher' THEN 0
                WHEN attribution_type = 'nominal' THEN 1
                ELSE 2
            END ASC,
            updated_at DESC,
            created_at DESC
        LIMIT 1;
        """
        
        attributions_result = None
        def _read_attributions(session):
            nonlocal attributions_result
            attributions_result = session.transaction().execute(query_attributions, commit_tx=True)
        
        firms_pool.retry_operation_sync(_read_attributions)
        
        dispatcher_percent = 0.0
        if attributions_result and attributions_result[0].rows:
            row = list(attributions_result[0].rows)[0]
            dispatcher_percent = row.percent_snapshot
        
        logger.info("analytics_getter.employee_finance_month_total.success", user_id=user_id, events_count=events_count)
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "month": month,
            "year": year,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "dispatcher_percent": dispatcher_percent,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_finance_month_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_month_total.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")


def handle_employee_finance_total(body, firm_id, events_pool, events_database, firms_pool, firms_database, logger, hlog):
    logger.info("analytics_getter.employee_finance_total.start", firm_id=firm_id)
    
    user_id = body.get("user_id")
    if not user_id:
        logger.warn("analytics_getter.employee_finance_total.missing_user_id")
        return bad_request("user_id is required")
    
    try:
        query_finance = f"""
        SELECT event_id, event_type, created_at
        FROM finance_events
        WHERE firm_id = '{firm_id}'
          AND event_type IN ('REWARD', 'FINE', 'SHIFT_END', 'DEAL_COMPLETE', 
                             'WITHHELD_SHIFT', 'WITHHOLD_ACCRUAL', 'ACCRUAL_DEFERRED')
        ORDER BY sequence_number ASC;
        """
        
        events_result = None
        def _read_events(session):
            nonlocal events_result
            events_result = session.transaction().execute(query_finance, commit_tx=True)
        
        events_pool.retry_operation_sync(_read_events)
        
        total_paid = 0
        total_pending = 0
        events_count = 0
        if events_result and events_result[0].rows:
            events_count = len(list(events_result[0].rows))
        
        query_attributions = f"""
        SELECT worker_user_id, dispatcher_id, percent_snapshot
        FROM dispatcher_attributions
        WHERE firm_id = '{firm_id}' AND worker_user_id = '{user_id}'
        ORDER BY
            CASE
                WHEN attribution_type = 'dispatcher' THEN 0
                WHEN attribution_type = 'nominal' THEN 1
                ELSE 2
            END ASC,
            updated_at DESC,
            created_at DESC
        LIMIT 1;
        """
        
        attributions_result = None
        def _read_attributions(session):
            nonlocal attributions_result
            attributions_result = session.transaction().execute(query_attributions, commit_tx=True)
        
        firms_pool.retry_operation_sync(_read_attributions)
        
        dispatcher_percent = 0.0
        if attributions_result and attributions_result[0].rows:
            row = list(attributions_result[0].rows)[0]
            dispatcher_percent = row.percent_snapshot
        
        logger.info("analytics_getter.employee_finance_total.success", user_id=user_id, events_count=events_count)
        
        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "dispatcher_percent": dispatcher_percent,
        })
        
    except Exception as e:
        logger.error("analytics_getter.employee_finance_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_finance_total.error", error=str(e))
        from utils import server_error
        return server_error("Internal Server Error")
