# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

import ydb

from utils.util_metadata import parse_json_value

from .shared import chunked, norm_str


def fetch_shift_rows_for_day(
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
        query = f"""
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
          s.tags_json AS tags_json,
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
            (
              s.status IN ('pending', 'active')
              AND (s.start_at IS NULL OR s.start_at < $end_at)
              AND (s.deadline_at IS NULL OR s.deadline_at >= $start_at)
            )
            OR
            (
              s.status IN ('cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND (
                (s.closed_at IS NOT NULL AND s.closed_at >= $start_at AND s.closed_at < $end_at)
                OR
                (s.closed_at IS NULL AND s.updated_at >= $start_at AND s.updated_at < $end_at)
              )
            )
          );
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
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
            tags = parse_json_value(getattr(row, "tags_json", None))
            rows_out.append(
                {
                    "shift_id": shift_id,
                    "event_id": shift_id,
                    "event_type": "shift",
                    "created_at": getattr(row, "updated_at", None)
                    or getattr(row, "created_at", None),
                    "worker_id": None,
                    "assigned_by": None,
                    "worker_profile": None,
                    "assigned_by_profile": None,
                    "shift": {
                        "shift_id": shift_id,
                        "object_id": norm_str(getattr(row, "object_id", None)),
                        "shift_name": norm_str(getattr(row, "shift_name", None)),
                        "base_payment": getattr(row, "base_payment", None),
                        "tags_json": tags if isinstance(tags, list) else [],
                        "deadline_at": getattr(row, "deadline_at", None),
                        "start_at": getattr(row, "start_at", None),
                        "opened_at": getattr(row, "opened_at", None),
                        "closed_at": getattr(row, "closed_at", None),
                        "status": norm_str(getattr(row, "status", None)).lower(),
                        "created_at": getattr(row, "created_at", None),
                        "updated_at": getattr(row, "updated_at", None),
                    },
                }
            )

    objects_pool.retry_operation_sync(_tx)
    return rows_out


def fetch_deal_rows_for_day(
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
        query = f"""
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
          d.norm_quantity AS norm_quantity,
          d.price_per_unit AS price_per_unit,
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
            (
              d.status IN ('active')
              AND (d.start_at IS NULL OR d.start_at < $end_at)
              AND (d.deadline_at IS NULL OR d.deadline_at >= $start_at)
            )
            OR
            (
              d.status IN ('archived', 'cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND d.updated_at >= $start_at AND d.updated_at < $end_at
            )
          );
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
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
                    "event_id": deal_id,
                    "event_type": "deal",
                    "created_at": getattr(row, "updated_at", None)
                    or getattr(row, "created_at", None),
                    "worker_id": None,
                    "assigned_by": None,
                    "worker_profile": None,
                    "assigned_by_profile": None,
                    "deal": {
                        "deal_id": deal_id,
                        "object_id": norm_str(getattr(row, "object_id", None)),
                        "deal_name": norm_str(getattr(row, "deal_name", None)),
                        "base_payment": getattr(row, "base_payment", None),
                        "norm_quantity": getattr(row, "norm_quantity", None),
                        "price_per_unit": getattr(row, "price_per_unit", None),
                        "deadline_at": getattr(row, "deadline_at", None),
                        "start_at": getattr(row, "start_at", None),
                        "status": norm_str(getattr(row, "status", None)).lower(),
                        "created_at": getattr(row, "created_at", None),
                        "updated_at": getattr(row, "updated_at", None),
                    },
                }
            )

    objects_pool.retry_operation_sync(_tx)
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
        query = f"""
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
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
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
        query = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $object_ids AS List<Utf8>;
        SELECT object_id, object_name, status, address_json
        FROM firm_objects
        WHERE firm_id = $firm_id
          AND object_id IN $object_ids;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
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


def fetch_user_profiles_map(
    *,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    user_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    ids = [uid for uid in (norm_str(x) for x in user_ids) if uid]
    if not ids:
        return {}

    out: Dict[str, Dict[str, Any]] = {}

    def _tx(session: ydb.Session, chunk_ids: List[str]):
        query = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $user_ids AS List<Utf8>;
        SELECT user_id, full_name, email, phone_number, tags_json
        FROM UserProfiles
        WHERE user_id IN $user_ids;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
            {"$user_ids": chunk_ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            user_id = norm_str(getattr(row, "user_id", None))
            if not user_id:
                continue
            tags = parse_json_value(getattr(row, "tags_json", None))
            out[user_id] = {
                "user_id": user_id,
                "full_name": getattr(row, "full_name", None),
                "email": getattr(row, "email", None),
                "phone_number": getattr(row, "phone_number", None),
                "tags_json": tags if isinstance(tags, list) else [],
            }

    for ids_chunk in chunked(ids, 200):
        firms_pool.retry_operation_sync(lambda s, _ids=ids_chunk: _tx(s, _ids))

    return out
