# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from utils import bad_request, ok_response, server_error

from handlers_employee_absences import (
    MAX_PAGE_SIZE,
    SOURCE_TYPE_ABSENCE,
    _extract_address_text,
    _extract_object_address_from_state,
    _extract_object_id_from_state,
    _normalize_str,
    _read_absence_disputes_by_event_ids,
    _read_absence_events,
    _read_objects_by_ids,
    _safe_int,
    _to_dispute_summary,
    _to_iso_utc,
)


def handle_employee_absences_month_details(
    body,
    firm_id,
    events_pool,
    events_database,
    objects_pool,
    objects_database,
    appeals_pool,
    appeals_database,
    meta_pool,
    meta_database,
    logger,
    hlog,
):
    logger.info("analytics_getter.employee_absences_month_details.start", firm_id=firm_id)

    user_id = body.get("user_id")
    month_raw = body.get("month")
    year_raw = body.get("year")

    if not user_id or month_raw is None or year_raw is None:
        logger.warn("analytics_getter.employee_absences_month_details.missing_params")
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
        logger.warn("analytics_getter.employee_absences_month_details.invalid_date", error=str(e))
        return bad_request("Invalid month or year")

    page = _safe_int(body.get("page"), 0)
    if page is None or page < 0:
        return bad_request("page must be an integer >= 0")

    requested_page_size = body.get("page_size")
    page_size = None
    if requested_page_size is not None:
        page_size = _safe_int(requested_page_size)
        if page_size is None or page_size < 1 or page_size > MAX_PAGE_SIZE:
            return bad_request(f"page_size must be an integer between 1 and {MAX_PAGE_SIZE}")

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
        user_absences.sort(
            key=lambda item: item.get("created_at") if isinstance(item.get("created_at"), datetime) else datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        monthly_absences = len(user_absences)

        effective_page_size = page_size if page_size is not None else (monthly_absences if monthly_absences > 0 else 1)
        start_index = page * effective_page_size
        end_index = min(start_index + effective_page_size, monthly_absences)
        if start_index >= monthly_absences:
            paged_absences = []
        else:
            paged_absences = user_absences[start_index:end_index]

        paged_event_ids = [
            _normalize_str(item.get("event_id"))
            for item in paged_absences
            if _normalize_str(item.get("event_id"))
        ]

        disputes_by_event = _read_absence_disputes_by_event_ids(
            appeals_pool=appeals_pool,
            appeals_database=appeals_database,
            firm_id=firm_id,
            user_id=user_id,
            event_ids=paged_event_ids,
        )

        object_ids = [
            _extract_object_id_from_state(item.get("state"))
            for item in paged_absences
            if _extract_object_id_from_state(item.get("state"))
        ]
        objects_map = _read_objects_by_ids(
            objects_pool=objects_pool,
            objects_database=objects_database,
            firm_id=firm_id,
            object_ids=object_ids,
        )

        absence_events = []
        unique_appeals: Dict[str, Dict[str, Any]] = {}
        for event in paged_absences:
            event_id = _normalize_str(event.get("event_id"))
            if not event_id:
                continue

            state = event.get("state") if isinstance(event.get("state"), dict) else {}
            metadata = dict(state) if isinstance(state, dict) else {}

            object_id = _extract_object_id_from_state(metadata)
            object_item = objects_map.get(object_id or "") if object_id else None

            object_name = _normalize_str((object_item or {}).get("object_name")) or None
            object_status = _normalize_str((object_item or {}).get("status")) or None
            object_address_json = (object_item or {}).get("address_json")
            object_address = _extract_address_text(object_address_json) or _extract_object_address_from_state(metadata)

            disputes = disputes_by_event.get(event_id) or []
            dispute_summary = _to_dispute_summary(disputes)
            latest_dispute = dispute_summary.get("latest_dispute") if isinstance(dispute_summary, dict) else None
            latest_appeal_id = _normalize_str((latest_dispute or {}).get("appeal_id"))
            if latest_appeal_id:
                metadata["dispute_appeal_id"] = latest_appeal_id
                metadata["appeal_id"] = latest_appeal_id
            if isinstance(latest_dispute, dict):
                metadata["dispute_status"] = latest_dispute.get("status")

            for item in disputes:
                appeal_id = _normalize_str(item.get("appeal_id"))
                if not appeal_id or appeal_id in unique_appeals:
                    continue
                unique_appeals[appeal_id] = {
                    "appeal_id": appeal_id,
                    "status": item.get("status"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "source_type": SOURCE_TYPE_ABSENCE,
                    "source_event_id": event_id,
                    "is_closed": bool(item.get("is_closed")),
                }

            absence_events.append(
                {
                    "event_id": event_id,
                    "event_type": event.get("event_type"),
                    "created_at": _to_iso_utc(event.get("created_at")),
                    "metadata": metadata,
                    "object_id": object_id,
                    "object_name": object_name,
                    "object_status": object_status,
                    "object_address": object_address,
                    "object_address_json": object_address_json if isinstance(object_address_json, dict) else None,
                    "dispute": dispute_summary,
                    "dispute_appeal_id": latest_appeal_id or None,
                    "appeal_id": latest_appeal_id or None,
                }
            )

        appeals_list = list(unique_appeals.values())
        appeals_list.sort(
            key=lambda item: item.get("created_at") or "",
            reverse=True,
        )

        total_pages = (
            (monthly_absences + effective_page_size - 1) // effective_page_size
            if monthly_absences > 0
            else 1
        )
        has_prev = page > 0 and monthly_absences > 0
        has_next = end_index < monthly_absences

        logger.info(
            "analytics_getter.employee_absences_month_details.success",
            user_id=user_id,
            absences_count=monthly_absences,
            page=page,
            page_size=effective_page_size,
            page_items=len(absence_events),
            appeals_count=len(appeals_list),
        )

        return ok_response(
            {
                "user_id": user_id,
                "firm_id": firm_id,
                "month": month,
                "year": year,
                "monthly_absences": monthly_absences,
                "page": page,
                "page_size": effective_page_size,
                "total": monthly_absences,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev,
                "absence_events": absence_events,
                "appeals": appeals_list,
            }
        )

    except Exception as e:
        logger.error("analytics_getter.employee_absences_month_details.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_month_details.error", error=str(e))
        return server_error("Internal Server Error")

