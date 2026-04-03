# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import ydb
from utils import ok_response, bad_request, server_error
from utils.util_metadata import parse_json_value

from constants import EVENT_TYPE_ABSENCE
from event_state import extract_user_id, fetch_firm_event_states

SOURCE_TYPE_ABSENCE = "absence"
DISPUTE_CLOSED_STATUSES = {"closed", "closed_unprocessed"}
MAX_PAGE_SIZE = 100


def _to_iso_utc(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (int, float)):
        try:
            ts = float(value)
            abs_ts = abs(ts)
            # Heuristic for unix timestamp units: sec / ms / micros.
            if abs_ts >= 1e14:
                ts = ts / 1_000_000.0
            elif abs_ts >= 1e11:
                ts = ts / 1_000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        except Exception:
            return str(value)
    return str(value)


def _normalize_str(value):
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except Exception:
            value = str(value)
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value, default=None):
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _chunked(values: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        return [values]
    return [values[i : i + chunk_size] for i in range(0, len(values), chunk_size)]


def _extract_object_id_from_state(state: Any) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in ("object_id", "obj_id"):
        value = _normalize_str(state.get(key))
        if value:
            return value
    obj_block = state.get("object")
    if isinstance(obj_block, dict):
        for key in ("object_id", "id"):
            value = _normalize_str(obj_block.get(key))
            if value:
                return value
    return None


def _extract_object_address_from_state(state: Any) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in ("object_address", "object_full_address", "address"):
        value = _normalize_str(state.get(key))
        if value:
            return value
    obj_block = state.get("object")
    if isinstance(obj_block, dict):
        for key in ("address", "full_address_text"):
            value = _normalize_str(obj_block.get(key))
            if value:
                return value
    return None


def _extract_address_text(address_json: Any) -> Optional[str]:
    if isinstance(address_json, dict):
        for key in ("full_address_text", "address", "value"):
            value = _normalize_str(address_json.get(key))
            if value:
                return value
    return None


def _read_objects_by_ids(
    *,
    objects_pool,
    objects_database,
    firm_id,
    object_ids: List[str],
):
    if not object_ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    unique_ids: List[str] = []
    seen: Set[str] = set()
    for object_id in object_ids:
        norm = _normalize_str(object_id)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_ids.append(norm)

    if not unique_ids:
        return {}

    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{objects_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $object_ids AS List<Utf8>;
            SELECT object_id, object_name, status, address_json
            FROM firm_objects
            WHERE firm_id = $firm_id
              AND object_id IN $object_ids;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id, "$object_ids": chunk},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                oid = _normalize_str(getattr(row, "object_id", None))
                if not oid:
                    continue
                address = parse_json_value(getattr(row, "address_json", None))
                out[oid] = {
                    "object_id": oid,
                    "object_name": _normalize_str(getattr(row, "object_name", None)),
                    "status": _normalize_str(getattr(row, "status", None)),
                    "address_json": address if isinstance(address, dict) else address,
                }

        objects_pool.retry_operation_sync(_tx)

    return out


def _read_absence_disputes_by_event_ids(
    *,
    appeals_pool,
    appeals_database,
    firm_id,
    user_id,
    event_ids: List[str],
):
    if not event_ids:
        return {}

    out: Dict[str, List[Dict[str, Any]]] = {}
    unique_ids: List[str] = []
    seen: Set[str] = set()
    for event_id in event_ids:
        norm = _normalize_str(event_id)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique_ids.append(norm)

    if not unique_ids:
        return {}

    normalized_user_id = _normalize_str(user_id)
    for chunk in _chunked(unique_ids, 200):
        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{appeals_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $source_type AS Utf8;
            DECLARE $source_event_ids AS List<Utf8>;
            SELECT appeal_id, status, user_id, created_at, updated_at, object_id, deal_id
            FROM Appeals
            WHERE firm_id = $firm_id
              AND user_id = $user_id
              AND shift_id = $source_type
              AND deal_id IN $source_event_ids
            ORDER BY created_at DESC;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {
                    "$firm_id": firm_id,
                    "$user_id": normalized_user_id,
                    "$source_type": SOURCE_TYPE_ABSENCE,
                    "$source_event_ids": chunk,
                },
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                source_event_id = _normalize_str(getattr(row, "deal_id", None))
                if not source_event_id:
                    continue
                status = _normalize_str(getattr(row, "status", None))
                item = {
                    "appeal_id": _normalize_str(getattr(row, "appeal_id", None)),
                    "status": status,
                    "is_closed": status.lower() in DISPUTE_CLOSED_STATUSES,
                    "user_id": _normalize_str(getattr(row, "user_id", None)),
                    "object_id": _normalize_str(getattr(row, "object_id", None)) or None,
                    "source_event_id": source_event_id,
                    "source_type": SOURCE_TYPE_ABSENCE,
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }
                out.setdefault(source_event_id, []).append(item)

        appeals_pool.retry_operation_sync(_tx)

    return out


def _to_dispute_summary(disputes: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = disputes if isinstance(disputes, list) else []
    latest = items[0] if items else None
    return {
        "has_dispute": len(items) > 0,
        "disputes_count": len(items),
        "latest_dispute": latest,
    }


def _read_absence_events(
    *,
    firm_id,
    user_id,
    events_pool,
    events_database,
    meta_pool,
    meta_database,
    logger,
    start_date=None,
    end_date=None,
):
    if start_date is None or end_date is None:
        query = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $event_type AS Utf8;
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type = $event_type
        ORDER BY sequence_number ASC;
        """
        params = {"$firm_id": firm_id, "$event_type": EVENT_TYPE_ABSENCE}
    else:
        query = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $event_type AS Utf8;
        DECLARE $start_date AS Timestamp;
        DECLARE $end_date AS Timestamp;
        SELECT event_id, event_type, created_at
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type = $event_type
          AND created_at >= $start_date
          AND created_at < $end_date
        ORDER BY sequence_number ASC;
        """
        params = {
            "$firm_id": firm_id,
            "$event_type": EVENT_TYPE_ABSENCE,
            "$start_date": start_date,
            "$end_date": end_date,
        }

    events_result = None

    def _read_events(session):
        nonlocal events_result
        events_result = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
            params,
            commit_tx=True,
        )

    events_pool.retry_operation_sync(_read_events)

    raw_events = []
    if events_result and events_result[0].rows:
        for row in events_result[0].rows:
            raw_events.append(
                {
                    "event_id": _normalize_str(getattr(row, "event_id", None)),
                    "event_type": _normalize_str(getattr(row, "event_type", None)),
                    "created_at": getattr(row, "created_at", None),
                }
            )

    event_ids = [event["event_id"] for event in raw_events if event.get("event_id")]
    event_states = {}
    if event_ids:
        event_states = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=firm_id,
            event_ids=event_ids,
            logger=logger,
        )

    user_absences = []
    normalized_user_id = _normalize_str(user_id)
    for event in raw_events:
        event_id = event.get("event_id")
        if not event_id:
            continue
        state = event_states.get(event_id)
        event_user_id = _normalize_str(extract_user_id(state))
        if event_user_id != normalized_user_id:
            continue
        user_absences.append(
            {
                "event_id": event_id,
                "event_type": event.get("event_type"),
                "created_at": event.get("created_at"),
                "state": state if isinstance(state, dict) else {},
            }
        )

    return user_absences


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

        return ok_response({
            "user_id": user_id,
            "firm_id": firm_id,
            "total_absences": total_absences,
        })

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
        return server_error("Internal Server Error")


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
                if not appeal_id:
                    continue
                if appeal_id in unique_appeals:
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

            absence_events.append({
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
            })

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

        return ok_response({
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
        })

    except Exception as e:
        logger.error("analytics_getter.employee_absences_month_details.error", error=str(e))
        hlog.exception("analytics_getter.employee_absences_month_details.error", error=str(e))
        return server_error("Internal Server Error")