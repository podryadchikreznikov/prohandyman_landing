# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import ydb

from utils import bad_request, forbidden, ok_response

from constants import EVENT_TYPE_WITHHOLD_ACCRUAL
from event_state import extract_amount_kopeks, extract_user_id, fetch_firm_event_states


def _parse_period(body: dict) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    year = body.get("year")
    month = body.get("month")

    if not isinstance(year, int) or year < 2020 or year > 2100:
        return None, None, "year must be an integer between 2020 and 2100"

    if month is None:
        return year, None, None

    if not isinstance(month, int) or month < 1 or month > 12:
        return None, None, "month must be an integer between 1 and 12"

    return year, month, None


def _period_range(*, year: int, month: Optional[int]) -> Tuple[datetime, datetime]:
    if month is None:
        return datetime(year, 1, 1, tzinfo=timezone.utc), datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _read_dispatcher_attributions(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    dispatcher_id: str,
) -> Dict[str, float]:
    out: Dict[str, float] = {}

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $dispatcher_id AS Utf8;
        SELECT worker_user_id, percent_snapshot
        FROM dispatcher_attributions
        WHERE firm_id = $firm_id AND dispatcher_id = $dispatcher_id
          AND attribution_type = 'dispatcher'
        ORDER BY updated_at DESC, created_at DESC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$dispatcher_id": dispatcher_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            worker_id = str(getattr(row, "worker_user_id", "") or "").strip()
            if not worker_id:
                continue
            if worker_id in out:
                continue
            try:
                out[worker_id] = float(getattr(row, "percent_snapshot", 0.0) or 0.0)
            except Exception:
                out[worker_id] = 0.0

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_worker_attributions_all_firms(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    dispatcher_id: str,
    worker_user_id: str,
) -> Dict[str, float]:
    """Return mapping firm_id -> percent_snapshot for a worker attributed to dispatcher across firms."""
    out: Dict[str, float] = {}

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $dispatcher_id AS Utf8;
        DECLARE $worker_user_id AS Utf8;
        SELECT firm_id, percent_snapshot
        FROM dispatcher_attributions
        WHERE dispatcher_id = $dispatcher_id AND worker_user_id = $worker_user_id
          AND attribution_type = 'dispatcher'
        ORDER BY updated_at DESC, created_at DESC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$dispatcher_id": dispatcher_id, "$worker_user_id": worker_user_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            firm = str(getattr(row, "firm_id", "") or "").strip()
            if not firm:
                continue
            if firm in out:
                continue
            try:
                out[firm] = float(getattr(row, "percent_snapshot", 0.0) or 0.0)
            except Exception:
                out[firm] = 0.0

    firms_pool.retry_operation_sync(_tx)
    return out


def _read_employee_status(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    firm_id: str,
    user_id: str,
) -> Optional[str]:
    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $user_id AS Utf8;
        SELECT status
        FROM firm_employees
        WHERE firm_id = $firm_id AND user_id = $user_id;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$user_id": user_id},
            commit_tx=True,
        )
        if not rs or not rs[0].rows:
            return None
        status = getattr(rs[0].rows[0], "status", None)
        if isinstance(status, bytes):
            status = status.decode("utf-8")
        return status.lower().strip() if isinstance(status, str) else None

    return firms_pool.retry_operation_sync(_tx)


def _read_withhold_events(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    start: datetime,
    end: datetime,
) -> List[str]:
    event_ids: List[str] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT event_id
        FROM finance_events
        WHERE firm_id = $firm_id
          AND event_type = '{EVENT_TYPE_WITHHOLD_ACCRUAL}'
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": start, "$end_at": end},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            eid = str(getattr(row, "event_id", "") or "").strip()
            if eid:
                event_ids.append(eid)

    events_pool.retry_operation_sync(_tx)
    return event_ids


def _read_withhold_events_all_time(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
) -> List[str]:
    event_ids: List[str] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        SELECT event_id
        FROM finance_events
        WHERE firm_id = $firm_id AND event_type = '{EVENT_TYPE_WITHHOLD_ACCRUAL}'
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            eid = str(getattr(row, "event_id", "") or "").strip()
            if eid:
                event_ids.append(eid)

    events_pool.retry_operation_sync(_tx)
    return event_ids


def handle_dispatcher_withhold_accrual_year_total(
    *,
    body: dict,
    firm_id: str,
    dispatcher_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.dispatcher.withhold_year_total.start", firm_id=firm_id, dispatcher_id=dispatcher_id)

    year, month, err = _parse_period(body)
    if err:
        return bad_request(err)
    start, end = _period_range(year=year, month=None)

    attributions = _read_dispatcher_attributions(
        firms_pool=firms_pool,
        firms_database=firms_database,
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
    )
    attributed_workers = set(attributions.keys())

    event_ids = _read_withhold_events(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    total_kopeks = 0
    matched_events = 0
    for eid, state in states.items():
        user_id = extract_user_id(state)
        if user_id not in attributed_workers:
            continue
        amount = extract_amount_kopeks(state)
        if isinstance(amount, int):
            total_kopeks += amount
            matched_events += 1

    logger.info(
        "analytics_getter.dispatcher.withhold_year_total.success",
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
        year=year,
        matched_events=matched_events,
        total_kopeks=total_kopeks,
    )

    return ok_response(
        {
            "firm_id": firm_id,
            "dispatcher_id": dispatcher_id,
            "year": year,
            "withhold_accrual_total_kopeks": total_kopeks,
            "events_count": matched_events,
            "attributions_count": len(attributions),
        }
    )


def handle_dispatcher_withhold_accrual_month_total(
    *,
    body: dict,
    firm_id: str,
    dispatcher_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.dispatcher.withhold_month_total.start", firm_id=firm_id, dispatcher_id=dispatcher_id)

    year, month, err = _parse_period(body)
    if err:
        return bad_request(err)
    if month is None:
        return bad_request("month is required")
    start, end = _period_range(year=year, month=month)

    attributions = _read_dispatcher_attributions(
        firms_pool=firms_pool,
        firms_database=firms_database,
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
    )
    attributed_workers = set(attributions.keys())

    event_ids = _read_withhold_events(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    total_kopeks = 0
    matched_events = 0
    for eid, state in states.items():
        user_id = extract_user_id(state)
        if user_id not in attributed_workers:
            continue
        amount = extract_amount_kopeks(state)
        if isinstance(amount, int):
            total_kopeks += amount
            matched_events += 1

    logger.info(
        "analytics_getter.dispatcher.withhold_month_total.success",
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
        year=year,
        month=month,
        matched_events=matched_events,
        total_kopeks=total_kopeks,
    )

    return ok_response(
        {
            "firm_id": firm_id,
            "dispatcher_id": dispatcher_id,
            "year": year,
            "month": month,
            "withhold_accrual_total_kopeks": total_kopeks,
            "events_count": matched_events,
            "attributions_count": len(attributions),
        }
    )


def handle_dispatcher_withhold_accrual_year_percent_avg(
    *,
    body: dict,
    firm_id: str,
    dispatcher_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.dispatcher.withhold_year_percent_avg.start", firm_id=firm_id, dispatcher_id=dispatcher_id)

    year, month, err = _parse_period(body)
    if err:
        return bad_request(err)
    start, end = _period_range(year=year, month=None)

    attributions = _read_dispatcher_attributions(
        firms_pool=firms_pool,
        firms_database=firms_database,
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
    )
    if not attributions:
        return ok_response(
            {
                "firm_id": firm_id,
                "dispatcher_id": dispatcher_id,
                "year": year,
                "percent_avg": 0.0,
                "attributions_count": 0,
                "workers_with_events_count": 0,
            }
        )

    event_ids = _read_withhold_events(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    workers_with_events = set()
    for state in states.values():
        uid = extract_user_id(state)
        if uid in attributions:
            workers_with_events.add(uid)

    percents = [attributions[uid] for uid in workers_with_events if uid in attributions]
    if not percents:
        percents = list(attributions.values())

    percent_avg = sum(percents) / len(percents) if percents else 0.0

    logger.info(
        "analytics_getter.dispatcher.withhold_year_percent_avg.success",
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
        year=year,
        percent_avg=percent_avg,
        attributions_count=len(attributions),
        workers_with_events_count=len(workers_with_events),
    )

    return ok_response(
        {
            "firm_id": firm_id,
            "dispatcher_id": dispatcher_id,
            "year": year,
            "percent_avg": percent_avg,
            "attributions_count": len(attributions),
            "workers_with_events_count": len(workers_with_events),
        }
    )


def handle_dispatcher_withhold_accrual_month_percent_avg(
    *,
    body: dict,
    firm_id: str,
    dispatcher_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.dispatcher.withhold_month_percent_avg.start", firm_id=firm_id, dispatcher_id=dispatcher_id)

    year, month, err = _parse_period(body)
    if err:
        return bad_request(err)
    if month is None:
        return bad_request("month is required")
    start, end = _period_range(year=year, month=month)

    attributions = _read_dispatcher_attributions(
        firms_pool=firms_pool,
        firms_database=firms_database,
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
    )
    if not attributions:
        return ok_response(
            {
                "firm_id": firm_id,
                "dispatcher_id": dispatcher_id,
                "year": year,
                "month": month,
                "percent_avg": 0.0,
                "attributions_count": 0,
                "workers_with_events_count": 0,
            }
        )

    event_ids = _read_withhold_events(
        events_pool=events_pool,
        events_database=events_database,
        firm_id=firm_id,
        start=start,
        end=end,
    )
    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    workers_with_events = set()
    for state in states.values():
        uid = extract_user_id(state)
        if uid in attributions:
            workers_with_events.add(uid)

    percents = [attributions[uid] for uid in workers_with_events if uid in attributions]
    if not percents:
        percents = list(attributions.values())

    percent_avg = sum(percents) / len(percents) if percents else 0.0

    logger.info(
        "analytics_getter.dispatcher.withhold_month_percent_avg.success",
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
        year=year,
        month=month,
        percent_avg=percent_avg,
        attributions_count=len(attributions),
        workers_with_events_count=len(workers_with_events),
    )

    return ok_response(
        {
            "firm_id": firm_id,
            "dispatcher_id": dispatcher_id,
            "year": year,
            "month": month,
            "percent_avg": percent_avg,
            "attributions_count": len(attributions),
            "workers_with_events_count": len(workers_with_events),
        }
    )


def handle_dispatcher_withhold_accrual_user_total(
    *,
    body: dict,
    firm_id: str,
    dispatcher_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    logger.info("analytics_getter.dispatcher.withhold_user_total.start", firm_id=firm_id, dispatcher_id=dispatcher_id)

    user_id = body.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    user_id = user_id.strip()

    year = body.get("year")
    month = body.get("month")
    if month is not None and year is None:
        return bad_request("year is required when month is provided")
    if year is not None and (not isinstance(year, int) or year < 2020 or year > 2100):
        return bad_request("year must be an integer between 2020 and 2100")
    if month is not None and (not isinstance(month, int) or month < 1 or month > 12):
        return bad_request("month must be an integer between 1 and 12")

    attributions = _read_dispatcher_attributions(
        firms_pool=firms_pool,
        firms_database=firms_database,
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
    )
    if user_id not in attributions:
        return forbidden("Forbidden")

    start = None
    end = None
    if isinstance(year, int) and month is None:
        start, end = _period_range(year=year, month=None)
    elif isinstance(year, int) and isinstance(month, int):
        start, end = _period_range(year=year, month=month)

    if start and end:
        event_ids = _read_withhold_events(
            events_pool=events_pool,
            events_database=events_database,
            firm_id=firm_id,
            start=start,
            end=end,
        )
    else:
        # all-time (no date filter)
        event_ids = []

        def _tx(session: ydb.Session):
            q = f"""
            PRAGMA TablePathPrefix('{events_database}');
            DECLARE $firm_id AS Utf8;
            SELECT event_id
            FROM finance_events
            WHERE firm_id = $firm_id AND event_type = '{EVENT_TYPE_WITHHOLD_ACCRUAL}'
            ORDER BY sequence_number ASC;
            """
            rs = session.transaction(ydb.OnlineReadOnly()).execute(
                session.prepare(q),
                {"$firm_id": firm_id},
                commit_tx=True,
            )
            rows = rs[0].rows if rs and rs[0].rows else []
            for row in rows:
                eid = str(getattr(row, "event_id", "") or "").strip()
                if eid:
                    event_ids.append(eid)

        events_pool.retry_operation_sync(_tx)

    states = fetch_firm_event_states(
        meta_pool=meta_pool,
        meta_database=meta_database,
        firm_id=firm_id,
        event_ids=event_ids,
        logger=logger,
    )

    total_kopeks = 0
    matched_events = 0
    for state in states.values():
        uid = extract_user_id(state)
        if uid != user_id:
            continue
        amount = extract_amount_kopeks(state)
        if isinstance(amount, int):
            total_kopeks += amount
            matched_events += 1

    resp = {
        "firm_id": firm_id,
        "dispatcher_id": dispatcher_id,
        "user_id": user_id,
        "percent_snapshot": attributions.get(user_id, 0.0),
        "withhold_accrual_total_kopeks": total_kopeks,
        "events_count": matched_events,
    }
    if isinstance(year, int):
        resp["year"] = year
    if isinstance(month, int):
        resp["month"] = month

    logger.info(
        "analytics_getter.dispatcher.withhold_user_total.success",
        firm_id=firm_id,
        dispatcher_id=dispatcher_id,
        user_id=user_id,
        matched_events=matched_events,
        total_kopeks=total_kopeks,
    )
    return ok_response(resp)


def handle_dispatcher_withhold_accrual_user_total_all_firms(
    *,
    body: dict,
    firm_id: str,
    dispatcher_id: str,
    events_pool: ydb.SessionPool,
    events_database: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    logger,
    hlog,
):
    """Cross-firm summary for a worker attributed to dispatcher.

    Firms set: those where (dispatcher_id, worker_user_id) exists in dispatcher_attributions
    AND worker is present in firm_employees with status in (active_unattached, active_attached).
    """
    logger.info(
        "analytics_getter.dispatcher.user_withhold_all_firms.start",
        context_firm_id=firm_id,
        dispatcher_id=dispatcher_id,
    )

    user_id = body.get("user_id")
    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    user_id = user_id.strip()

    year = body.get("year")
    month = body.get("month")
    if month is not None and year is None:
        return bad_request("year is required when month is provided")
    if year is not None and (not isinstance(year, int) or year < 2020 or year > 2100):
        return bad_request("year must be an integer between 2020 and 2100")
    if month is not None and (not isinstance(month, int) or month < 1 or month > 12):
        return bad_request("month must be an integer between 1 and 12")

    attributions_by_firm = _read_worker_attributions_all_firms(
        firms_pool=firms_pool,
        firms_database=firms_database,
        dispatcher_id=dispatcher_id,
        worker_user_id=user_id,
    )
    if not attributions_by_firm:
        return forbidden("Forbidden")

    start = None
    end = None
    if isinstance(year, int) and month is None:
        start, end = _period_range(year=year, month=None)
    elif isinstance(year, int) and isinstance(month, int):
        start, end = _period_range(year=year, month=month)

    firms_summary: List[dict] = []
    total_kopeks = 0
    total_events = 0
    firms_with_events = 0

    for attributed_firm_id, percent_snapshot in attributions_by_firm.items():
        status = _read_employee_status(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=attributed_firm_id,
            user_id=user_id,
        )
        if status not in ("active_unattached", "active_attached"):
            continue

        if start and end:
            event_ids = _read_withhold_events(
                events_pool=events_pool,
                events_database=events_database,
                firm_id=attributed_firm_id,
                start=start,
                end=end,
            )
        else:
            event_ids = _read_withhold_events_all_time(
                events_pool=events_pool,
                events_database=events_database,
                firm_id=attributed_firm_id,
            )

        states = fetch_firm_event_states(
            meta_pool=meta_pool,
            meta_database=meta_database,
            firm_id=attributed_firm_id,
            event_ids=event_ids,
            logger=logger,
        )

        firm_total = 0
        firm_events = 0
        for state in states.values():
            uid = extract_user_id(state)
            if uid != user_id:
                continue
            amount = extract_amount_kopeks(state)
            if isinstance(amount, int):
                firm_total += amount
                firm_events += 1

        if firm_events:
            firms_with_events += 1

        total_kopeks += firm_total
        total_events += firm_events

        firms_summary.append(
            {
                "firm_id": attributed_firm_id,
                "employee_status": status,
                "percent_snapshot": percent_snapshot,
                "withhold_accrual_total_kopeks": firm_total,
                "events_count": firm_events,
            }
        )

    percents = [item["percent_snapshot"] for item in firms_summary if item.get("events_count")]
    if not percents:
        percents = [item["percent_snapshot"] for item in firms_summary]

    percent_avg = sum(percents) / len(percents) if percents else 0.0

    resp = {
        "firm_id": firm_id,
        "dispatcher_id": dispatcher_id,
        "user_id": user_id,
        "percent_avg": percent_avg,
        "withhold_accrual_total_kopeks": total_kopeks,
        "events_count": total_events,
        "firms_count": len(firms_summary),
        "firms_with_events_count": firms_with_events,
        "firms": firms_summary,
    }
    if isinstance(year, int):
        resp["year"] = year
    if isinstance(month, int):
        resp["month"] = month

    logger.info(
        "analytics_getter.dispatcher.user_withhold_all_firms.success",
        dispatcher_id=dispatcher_id,
        user_id=user_id,
        firms_count=len(firms_summary),
        firms_with_events=firms_with_events,
        total_events=total_events,
        total_kopeks=total_kopeks,
        percent_avg=percent_avg,
    )

    return ok_response(resp)
