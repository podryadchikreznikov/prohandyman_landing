# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import ydb

from utils import bad_request, forbidden, ok_response

import handlers_worker_home as base


def handle_worker_fines_totals_all_firms(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info(
        "analytics_getter.worker.fines_totals_all_firms.start",
        context_firm_id=firm_id,
        caller_user_id=caller_user_id,
    )
    body_user_id = body.get("user_id")
    if body_user_id is not None and str(body_user_id) != caller_user_id:
        return forbidden("Forbidden")

    ref_year, ref_month, validation_error = base._validate_year_month_filters(body=body)
    if validation_error:
        return bad_request(validation_error)

    now = datetime.now(timezone.utc)
    if ref_year is None:
        ref_year = now.year
    if ref_month is None:
        ref_month = now.month

    memberships = base._read_worker_memberships_all_firms(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_id=caller_user_id,
    )
    if not memberships:
        return forbidden("Forbidden")

    all_time_start = datetime(1970, 1, 1, tzinfo=timezone.utc)
    all_time_end = now + timedelta(days=1)

    totals_all_time_kopeks = 0
    totals_year_kopeks = 0
    totals_month_kopeks = 0
    totals_all_time_events = 0
    totals_year_events = 0
    totals_month_events = 0
    firms_summary: List[Dict[str, Any]] = []

    for membership in memberships:
        firm_fines = base._build_worker_fines_for_firm(
            user_id=caller_user_id,
            firm_id=membership["firm_id"],
            firm_name=membership["firm_name"],
            employee_status=membership["employee_status"],
            start=all_time_start,
            end=all_time_end,
            events_pool=events_pool,
            events_database=events_database,
            meta_pool=meta_pool,
            meta_database=meta_database,
            logger=logger,
        )

        firm_all_time_kopeks = 0
        firm_year_kopeks = 0
        firm_month_kopeks = 0
        firm_all_time_events = 0
        firm_year_events = 0
        firm_month_events = 0
        for fine in firm_fines:
            amount_kopeks = fine.get("amount_kopeks")
            created_at_dt = fine.get("_created_at_dt")
            if not isinstance(amount_kopeks, int):
                continue
            firm_all_time_kopeks += amount_kopeks
            firm_all_time_events += 1
            if isinstance(created_at_dt, datetime) and created_at_dt.year == ref_year:
                firm_year_kopeks += amount_kopeks
                firm_year_events += 1
                if created_at_dt.month == ref_month:
                    firm_month_kopeks += amount_kopeks
                    firm_month_events += 1

        totals_all_time_kopeks += firm_all_time_kopeks
        totals_year_kopeks += firm_year_kopeks
        totals_month_kopeks += firm_month_kopeks
        totals_all_time_events += firm_all_time_events
        totals_year_events += firm_year_events
        totals_month_events += firm_month_events

        firms_summary.append(
            {
                "firm_id": membership["firm_id"],
                "firm_name": membership["firm_name"],
                "employee_status": membership["employee_status"],
                "totals": {
                    "all_time_kopeks": firm_all_time_kopeks,
                    "year_kopeks": firm_year_kopeks,
                    "month_kopeks": firm_month_kopeks,
                    "all_time_events_count": firm_all_time_events,
                    "year_events_count": firm_year_events,
                    "month_events_count": firm_month_events,
                },
            }
        )

    firms_with_fines_count = 0
    for item in firms_summary:
        totals = item.get("totals") if isinstance(item, dict) else None
        if isinstance(totals, dict) and int(totals.get("all_time_events_count") or 0) > 0:
            firms_with_fines_count += 1

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "reference_year": ref_year,
            "reference_month": ref_month,
            "totals": {
                "all_time_kopeks": totals_all_time_kopeks,
                "year_kopeks": totals_year_kopeks,
                "month_kopeks": totals_month_kopeks,
                "all_time_events_count": totals_all_time_events,
                "year_events_count": totals_year_events,
                "month_events_count": totals_month_events,
            },
            "firms_count": len(firms_summary),
            "firms_with_fines_count": firms_with_fines_count,
            "firms": firms_summary,
        }
    )


def handle_worker_fines_list_all_firms(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    appeals_pool: ydb.SessionPool,
    appeals_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info(
        "analytics_getter.worker.fines_list_all_firms.start",
        context_firm_id=firm_id,
        caller_user_id=caller_user_id,
    )
    body_user_id = body.get("user_id")
    if body_user_id is not None and str(body_user_id) != caller_user_id:
        return forbidden("Forbidden")

    page = body.get("page", 0)
    page_size = body.get("page_size", 20)
    if not isinstance(page, int) or page < 0:
        return bad_request("page must be a non-negative integer")
    if not isinstance(page_size, int) or page_size < 1 or page_size > 100:
        return bad_request("page_size must be an integer between 1 and 100")

    year, month, validation_error = base._validate_year_month_filters(body=body)
    if validation_error:
        return bad_request(validation_error)

    if isinstance(year, int) and isinstance(month, int):
        start, end = base._month_range(year=year, month=month)
    elif isinstance(year, int):
        start, end = base._year_range(year=year)
    else:
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) + timedelta(days=1)

    memberships = base._read_worker_memberships_all_firms(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_id=caller_user_id,
    )
    if not memberships:
        return forbidden("Forbidden")

    all_fines: List[Dict[str, Any]] = []
    for membership in memberships:
        all_fines.extend(
            base._build_worker_fines_for_firm(
                user_id=caller_user_id,
                firm_id=membership["firm_id"],
                firm_name=membership["firm_name"],
                employee_status=membership["employee_status"],
                start=start,
                end=end,
                events_pool=events_pool,
                events_database=events_database,
                meta_pool=meta_pool,
                meta_database=meta_database,
                logger=logger,
            )
        )

    all_fines.sort(
        key=lambda item: (
            item.get("_created_at_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            item.get("event_id") or "",
        ),
        reverse=True,
    )

    total = len(all_fines)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_items = all_fines[start_idx:end_idx]

    object_ids_by_firm: Dict[str, List[str]] = {}
    event_ids_by_firm: Dict[str, List[str]] = {}
    for item in page_items:
        firm_data = item.get("firm") if isinstance(item.get("firm"), dict) else {}
        firm_key = base._norm_text(firm_data.get("firm_id"))
        if not firm_key:
            continue
        object_id = base._norm_text(item.get("object_id"))
        if object_id:
            object_ids_by_firm.setdefault(firm_key, []).append(object_id)
        event_id = base._norm_text(item.get("event_id"))
        if event_id:
            event_ids_by_firm.setdefault(firm_key, []).append(event_id)

    objects_map_by_firm: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for firm_key, object_ids in object_ids_by_firm.items():
        objects_map_by_firm[firm_key] = base._read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_key,
            object_ids=object_ids,
        )

    disputes_map_by_firm: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for firm_key, event_ids in event_ids_by_firm.items():
        disputes_map_by_firm[firm_key] = base._read_fine_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_key,
            event_ids=event_ids,
        )

    response_fines: List[Dict[str, Any]] = []
    for item in page_items:
        firm_data = item.get("firm") if isinstance(item.get("firm"), dict) else {}
        firm_key = base._norm_text(firm_data.get("firm_id"))
        object_id = base._norm_text(item.get("object_id"))
        event_id = base._norm_text(item.get("event_id"))

        object_info = None
        if firm_key and object_id:
            object_info = (objects_map_by_firm.get(firm_key) or {}).get(object_id)

        disputes = []
        if firm_key and event_id:
            disputes = (disputes_map_by_firm.get(firm_key) or {}).get(event_id) or []

        response_fines.append(
            {
                "event_id": item.get("event_id"),
                "event_type": item.get("event_type"),
                "created_at": item.get("created_at"),
                "amount_kopeks": item.get("amount_kopeks"),
                "theme": item.get("theme"),
                "message": item.get("message"),
                "state": item.get("state"),
                "firm": item.get("firm"),
                "object_id": item.get("object_id"),
                "object": object_info,
                "dispute": base._to_fine_dispute_summary(disputes),
            }
        )

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_more": end_idx < total,
            "year": year,
            "month": month,
            "fines": response_fines,
        }
    )


def handle_worker_absences_list_all_firms(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    appeals_pool: ydb.SessionPool,
    appeals_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info(
        "analytics_getter.worker.absences_list_all_firms.start",
        context_firm_id=firm_id,
        caller_user_id=caller_user_id,
    )
    body_user_id = body.get("user_id")
    if body_user_id is not None and str(body_user_id) != caller_user_id:
        return forbidden("Forbidden")

    page = body.get("page", 0)
    page_size = body.get("page_size", 20)
    if not isinstance(page, int) or page < 0:
        return bad_request("page must be a non-negative integer")
    if not isinstance(page_size, int) or page_size < 1 or page_size > 100:
        return bad_request("page_size must be an integer between 1 and 100")

    year, month, validation_error = base._validate_year_month_filters(body=body)
    if validation_error:
        return bad_request(validation_error)

    if isinstance(year, int) and isinstance(month, int):
        start, end = base._month_range(year=year, month=month)
    elif isinstance(year, int):
        start, end = base._year_range(year=year)
    else:
        start = datetime(1970, 1, 1, tzinfo=timezone.utc)
        end = datetime.now(timezone.utc) + timedelta(days=1)

    memberships = base._read_worker_memberships_all_firms(
        firms_pool=firms_pool,
        firms_database=firms_database,
        user_id=caller_user_id,
    )
    if not memberships:
        return forbidden("Forbidden")

    all_absences: List[Dict[str, Any]] = []
    for membership in memberships:
        all_absences.extend(
            base._build_worker_absences_for_firm(
                user_id=caller_user_id,
                firm_id=membership["firm_id"],
                firm_name=membership["firm_name"],
                employee_status=membership["employee_status"],
                start=start,
                end=end,
                events_pool=events_pool,
                events_database=events_database,
                meta_pool=meta_pool,
                meta_database=meta_database,
                logger=logger,
            )
        )

    all_absences.sort(
        key=lambda item: (
            item.get("_created_at_dt") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            item.get("event_id") or "",
        ),
        reverse=True,
    )

    total = len(all_absences)
    start_idx = page * page_size
    end_idx = start_idx + page_size
    page_items = all_absences[start_idx:end_idx]

    object_ids_by_firm: Dict[str, List[str]] = {}
    event_ids_by_firm: Dict[str, List[str]] = {}
    for item in page_items:
        firm_data = item.get("firm") if isinstance(item.get("firm"), dict) else {}
        firm_key = base._norm_text(firm_data.get("firm_id"))
        if not firm_key:
            continue
        object_id = base._norm_text(item.get("object_id"))
        if object_id:
            object_ids_by_firm.setdefault(firm_key, []).append(object_id)
        event_id = base._norm_text(item.get("event_id"))
        if event_id:
            event_ids_by_firm.setdefault(firm_key, []).append(event_id)

    objects_map_by_firm: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for firm_key, object_ids in object_ids_by_firm.items():
        objects_map_by_firm[firm_key] = base._read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_key,
            object_ids=object_ids,
        )

    disputes_map_by_firm: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for firm_key, event_ids in event_ids_by_firm.items():
        disputes_map_by_firm[firm_key] = base._read_absence_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_key,
            user_id=caller_user_id,
            event_ids=event_ids,
        )

    response_absences: List[Dict[str, Any]] = []
    for item in page_items:
        firm_data = item.get("firm") if isinstance(item.get("firm"), dict) else {}
        firm_key = base._norm_text(firm_data.get("firm_id"))
        object_id = base._norm_text(item.get("object_id"))
        event_id = base._norm_text(item.get("event_id"))

        object_info = None
        if firm_key and object_id:
            object_info = (objects_map_by_firm.get(firm_key) or {}).get(object_id)

        disputes = []
        if firm_key and event_id:
            disputes = (disputes_map_by_firm.get(firm_key) or {}).get(event_id) or []
        dispute_summary = base._to_absence_dispute_summary(disputes)
        latest_dispute = dispute_summary.get("latest_dispute") if isinstance(dispute_summary, dict) else None
        latest_appeal_id = base._norm_text((latest_dispute or {}).get("appeal_id"))

        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        metadata_out = dict(metadata)
        if latest_appeal_id:
            metadata_out["dispute_appeal_id"] = latest_appeal_id
            metadata_out["appeal_id"] = latest_appeal_id
        if isinstance(latest_dispute, dict):
            metadata_out["dispute_status"] = latest_dispute.get("status")

        object_name = base._norm_text((object_info or {}).get("object_name")) or None
        object_address_json = (object_info or {}).get("address_json")
        object_address = (
            base._extract_address_text(object_address_json)
            or base._norm_text(item.get("object_address"))
            or base._extract_object_address_from_state(metadata_out)
            or None
        )

        response_absences.append(
            {
                "event_id": item.get("event_id"),
                "event_type": item.get("event_type"),
                "created_at": item.get("created_at"),
                "metadata": metadata_out,
                "state": metadata_out,
                "firm": item.get("firm"),
                "object_id": item.get("object_id"),
                "object": object_info,
                "object_name": object_name,
                "object_address": object_address,
                "shift_start_at": item.get("shift_start_at"),
                "shift_end_at": item.get("shift_end_at"),
                "dispute": dispute_summary,
                "dispute_appeal_id": latest_appeal_id or None,
                "appeal_id": latest_appeal_id or None,
            }
        )

    return ok_response(
        {
            "firm_id": firm_id,
            "user_id": caller_user_id,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_more": end_idx < total,
            "year": year,
            "month": month,
            "absences": response_absences,
        }
    )