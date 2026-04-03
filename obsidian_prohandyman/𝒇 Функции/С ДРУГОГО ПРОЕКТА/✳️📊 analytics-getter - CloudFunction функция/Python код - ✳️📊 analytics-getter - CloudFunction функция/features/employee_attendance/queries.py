# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

import ydb

from .shared import norm_str


ATTENDANCE_EVENT_TYPES = (
    "obj_enter",
    "obj_leave",
    "shift_assign",
    "shift_start",
    "shift_end",
    "shift_cancel",
    "shift_refuse",
    "deal_assign",
    "deal_complete",
    "deal_force_end",
    "deal_cancel",
    "deal_refuse",
)


def fetch_shift_rows_for_window(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    start_at,
    end_at,
    object_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        DECLARE $object_id AS Utf8?;

        SELECT
          s.shift_id AS shift_id,
          s.object_id AS object_id,
          s.shift_name AS shift_name,
          s.base_payment AS base_payment,
          s.deadline_at AS deadline_at,
          s.start_at AS start_at,
          s.opened_at AS opened_at,
          s.closed_at AS closed_at,
          s.status AS status,
          s.created_at AS created_at,
          s.updated_at AS updated_at
        FROM firm_shifts AS s
        INNER JOIN firm_objects AS o ON o.object_id = s.object_id
        WHERE o.firm_id = $firm_id
          AND ($object_id IS NULL OR s.object_id = $object_id)
          AND (
            (s.start_at IS NOT NULL AND s.start_at < $end_at AND (s.deadline_at IS NULL OR s.deadline_at >= $start_at))
            OR (s.opened_at IS NOT NULL AND s.opened_at < $end_at AND (s.closed_at IS NULL OR s.closed_at >= $start_at))
            OR (s.deadline_at IS NOT NULL AND s.deadline_at >= $start_at AND s.deadline_at < $end_at)
            OR (s.closed_at IS NOT NULL AND s.closed_at >= $start_at AND s.closed_at < $end_at)
            OR (s.updated_at >= $start_at AND s.updated_at < $end_at)
            OR (s.created_at >= $start_at AND s.created_at < $end_at)
          );
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {
                "$firm_id": firm_id,
                "$start_at": start_at,
                "$end_at": end_at,
                "$object_id": norm_str(object_id) or None,
            },
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            shift_id = norm_str(getattr(row, "shift_id", None))
            if not shift_id:
                continue
            rows_out.append(
                {
                    "shift_id": shift_id,
                    "object_id": norm_str(getattr(row, "object_id", None)),
                    "shift_name": norm_str(getattr(row, "shift_name", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "deadline_at": getattr(row, "deadline_at", None),
                    "start_at": getattr(row, "start_at", None),
                    "opened_at": getattr(row, "opened_at", None),
                    "closed_at": getattr(row, "closed_at", None),
                    "status": norm_str(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return rows_out


def fetch_deal_rows_for_window(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    start_at,
    end_at,
    object_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        DECLARE $object_id AS Utf8?;

        SELECT
          d.deal_id AS deal_id,
          d.object_id AS object_id,
          d.deal_name AS deal_name,
          d.base_payment AS base_payment,
          d.deadline_at AS deadline_at,
          d.start_at AS start_at,
          d.status AS status,
          d.created_at AS created_at,
          d.updated_at AS updated_at
        FROM firm_deals AS d
        INNER JOIN firm_objects AS o ON o.object_id = d.object_id
        WHERE o.firm_id = $firm_id
          AND ($object_id IS NULL OR d.object_id = $object_id)
          AND (
            (d.start_at IS NOT NULL AND d.start_at < $end_at AND (d.deadline_at IS NULL OR d.deadline_at >= $start_at))
            OR (d.deadline_at IS NOT NULL AND d.deadline_at >= $start_at AND d.deadline_at < $end_at)
            OR (d.updated_at >= $start_at AND d.updated_at < $end_at)
            OR (d.created_at >= $start_at AND d.created_at < $end_at)
          );
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {
                "$firm_id": firm_id,
                "$start_at": start_at,
                "$end_at": end_at,
                "$object_id": norm_str(object_id) or None,
            },
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            deal_id = norm_str(getattr(row, "deal_id", None))
            if not deal_id:
                continue
            rows_out.append(
                {
                    "deal_id": deal_id,
                    "object_id": norm_str(getattr(row, "object_id", None)),
                    "deal_name": norm_str(getattr(row, "deal_name", None)),
                    "base_payment": getattr(row, "base_payment", None),
                    "deadline_at": getattr(row, "deadline_at", None),
                    "start_at": getattr(row, "start_at", None),
                    "status": norm_str(getattr(row, "status", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return rows_out


def fetch_object_event_rows_for_window(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    start_at,
    end_at,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at, updated_at, sequence_number
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type IN (
            'obj_enter', 'obj_leave',
            'shift_assign', 'shift_start', 'shift_end', 'shift_cancel', 'shift_refuse',
            'deal_assign', 'deal_complete', 'deal_force_end', 'deal_cancel', 'deal_refuse'
          )
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = norm_str(getattr(row, "event_id", None))
            if not event_id:
                continue
            rows_out.append(
                {
                    "event_id": event_id,
                    "event_type": norm_str(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return rows_out


def fetch_assign_event_rows_before(
    *,
    events_pool: ydb.SessionPool,
    events_database: str,
    firm_id: str,
    end_at,
) -> List[Dict[str, Any]]:
    rows_out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at, updated_at, sequence_number
        FROM object_events
        WHERE firm_id = $firm_id
          AND event_type IN ('shift_assign', 'deal_assign')
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = norm_str(getattr(row, "event_id", None))
            if not event_id:
                continue
            rows_out.append(
                {
                    "event_id": event_id,
                    "event_type": norm_str(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "updated_at": getattr(row, "updated_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return rows_out


def fetch_object_rows_by_ids(
    *,
    objects_pool: ydb.SessionPool,
    objects_database: str,
    firm_id: str,
    object_ids: List[str],
) -> List[Dict[str, Any]]:
    normalized_ids = [norm_str(value) for value in object_ids if norm_str(value)]
    if not normalized_ids:
        return []

    rows_out: List[Dict[str, Any]] = []

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
        rs = session.transaction().execute(
            session.prepare(q),
            {"$firm_id": firm_id, "$object_ids": normalized_ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            object_id = norm_str(getattr(row, "object_id", None))
            if not object_id:
                continue
            rows_out.append(
                {
                    "object_id": object_id,
                    "object_name": norm_str(getattr(row, "object_name", None)),
                    "status": norm_str(getattr(row, "status", None)).lower(),
                    "address_json": getattr(row, "address_json", None),
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return rows_out
