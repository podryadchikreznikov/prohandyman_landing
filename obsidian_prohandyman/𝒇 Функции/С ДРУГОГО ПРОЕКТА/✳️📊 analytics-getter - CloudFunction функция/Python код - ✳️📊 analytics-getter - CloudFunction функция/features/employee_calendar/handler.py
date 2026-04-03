# -*- coding: utf-8 -*-
from __future__ import annotations

from utils import bad_request, ok_response, server_error

from .pipeline import build_employee_calendar_day_dataset
from .shared import norm_str


def _base_response(dataset: dict, section: str) -> dict:
    selected = dataset.get(section) or {}
    return {
        "user_id": dataset["user_id"],
        "firm_id": dataset["firm_id"],
        "date": dataset["date"],
        "selected_object_id": dataset.get("selected_object_id"),
        "shifts": selected.get("shifts", []),
        "deals": selected.get("deals", []),
        "user_profiles": dataset.get("user_profiles", {}),
    }


def handle_employee_calendar_day_upcoming(
    *,
    body,
    firm_id,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_calendar_day_upcoming.start", firm_id=firm_id)

    user_id = norm_str(body.get("user_id"))
    date_str = norm_str(body.get("date"))
    object_id = norm_str(body.get("object_id"))

    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_calendar_day_upcoming.missing_params")
        return bad_request("user_id and date are required")

    try:
        dataset = build_employee_calendar_day_dataset(
            firm_id=firm_id,
            user_id=user_id,
            date_str=date_str,
            object_id=object_id or None,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        response = _base_response(dataset, "upcoming")
        logger.info(
            "analytics_getter.employee_calendar_day_upcoming.success",
            user_id=user_id,
            date=date_str,
            shifts_count=len(response["shifts"]),
            deals_count=len(response["deals"]),
        )
        return ok_response(response)
    except Exception as error:
        logger.error("analytics_getter.employee_calendar_day_upcoming.error", error=str(error))
        hlog.exception("analytics_getter.employee_calendar_day_upcoming.error", error=str(error))
        return server_error("Internal Server Error")


def handle_employee_calendar_day_period(
    *,
    body,
    firm_id,
    objects_pool,
    objects_database,
    firms_pool,
    firms_database,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_calendar_day_period.start", firm_id=firm_id)

    user_id = norm_str(body.get("user_id"))
    date_str = norm_str(body.get("date"))
    object_id = norm_str(body.get("object_id"))

    if not user_id or not date_str:
        logger.warn("analytics_getter.employee_calendar_day_period.missing_params")
        return bad_request("user_id and date are required")

    try:
        dataset = build_employee_calendar_day_dataset(
            firm_id=firm_id,
            user_id=user_id,
            date_str=date_str,
            object_id=object_id or None,
            objects_pool=objects_pool,
            objects_database=objects_database,
            firms_pool=firms_pool,
            firms_database=firms_database,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )
        response = _base_response(dataset, "period")
        logger.info(
            "analytics_getter.employee_calendar_day_period.success",
            user_id=user_id,
            date=date_str,
            shifts_count=len(response["shifts"]),
            deals_count=len(response["deals"]),
        )
        return ok_response(response)
    except Exception as error:
        logger.error("analytics_getter.employee_calendar_day_period.error", error=str(error))
        hlog.exception("analytics_getter.employee_calendar_day_period.error", error=str(error))
        return server_error("Internal Server Error")
