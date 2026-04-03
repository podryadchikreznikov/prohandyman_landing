# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone

from utils import bad_request, ok_response, server_error

from handlers_employee_absences import (
    _normalize_str,
    _read_absence_disputes_by_event_ids,
    _read_absence_events,
)


def handle_employee_absences_total(body, firm_id, events_pool, events_database, meta_pool, meta_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_total.start", firm_id=firm_id)

    user_id = body.get("user_id")
    if not user_id:
        logger.warn("analytics_getter.employee_absences_total.missing_user_id")
        return bad_request("user_id is required")

    try:
        user_absences = _read_absence_events(
            firm_id=firm_id,
            user_id=user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        total_absences = len(user_absences)

        logger.info("analytics_getter.employee_absences_total.success", user_id=user_id, total=total_absences)

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "total_absences": total_absences,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_absences_total.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_total.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_absences_disputed(body, firm_id, events_pool, events_database, appeals_pool, appeals_database, meta_pool, meta_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_disputed.start", firm_id=firm_id)

    user_id = body.get("user_id")
    if not user_id:
        logger.warn("analytics_getter.employee_absences_disputed.missing_user_id")
        return bad_request("user_id is required")

    try:
        user_absences = _read_absence_events(
            firm_id=firm_id,
            user_id=user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        total_absences = len(user_absences)

        event_ids = [item.get("event_id") for item in user_absences if _normalize_str(item.get("event_id"))]
        disputes_by_event = _read_absence_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_id,
            user_id=user_id,
            event_ids=event_ids,
        )
        disputed_count = sum(
            1 for event_id in event_ids if (disputes_by_event.get(_normalize_str(event_id)) or [])
        )

        logger.info(
            "analytics_getter.employee_absences_disputed.success",
            user_id=user_id,
            total=total_absences,
            disputed=disputed_count,
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "total_absences": total_absences,
                "disputed_absences": disputed_count,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_absences_disputed.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_disputed.error", error=str(e))
        return server_error("Internal Server Error")


def handle_employee_absences_month(body, firm_id, events_pool, events_database, meta_pool, meta_database, logger, hlog):
    logger.info("analytics_getter.employee_absences_month.start", firm_id=firm_id)

    user_id = body.get("user_id")
    month_raw = body.get("month")
    year_raw = body.get("year")

    if not user_id or month_raw is None or year_raw is None:
        logger.warn("analytics_getter.employee_absences_month.missing_params")
        return bad_request("user_id, month, and year are required")

    try:
        month = int(month_raw)
        year = int(year_raw)
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    except ValueError as e:
        logger.warn("analytics_getter.employee_absences_month.invalid_date", error=str(e))
        return bad_request("Invalid month or year")

    try:
        user_absences = _read_absence_events(
            firm_id=firm_id,
            user_id=user_id,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
            start_date=start_date,
            end_date=end_date,
        )
        monthly_absences = len(user_absences)

        logger.info(
            "analytics_getter.employee_absences_month.success",
            user_id=user_id,
            month=month,
            year=year,
            total=monthly_absences,
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "monthly_absences": monthly_absences,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_absences_month.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_month.error", error=str(e))
        return server_error("Internal Server Error")

