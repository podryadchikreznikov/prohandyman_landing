# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Tuple

from common import safe_json
from constants import EVENT_TYPE_OBJ_ENTER, EVENT_TYPE_OBJ_LEAVE
from event_state import extract_user_id

from .shared import norm_ids, norm_str, normalize_ids_list, to_iso_utc


def fetch_object_employee_rows(*, firms_pool, firms_database, firm_id, object_id):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $firm_id AS Utf8;
        SELECT user_id, object_ids, role_type, status
        FROM firm_employees
        WHERE firm_id = $firm_id;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$firm_id": firm_id},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            status = norm_str(getattr(row, "status", None)).lower()
            if not status.startswith("active_"):
                continue
            object_ids = normalize_ids_list(getattr(row, "object_ids", None))
            if object_id not in object_ids:
                continue
            user_id = norm_str(getattr(row, "user_id", None))
            if not user_id:
                continue
            result.append(
                {
                    "user_id": user_id,
                    "role_type": norm_str(getattr(row, "role_type", None)).lower(),
                    "status": status,
                }
            )

    firms_pool.retry_operation_sync(_tx)
    return result


def fetch_object_shifts_for_day(
    *, objects_pool, objects_database, object_id, start_at, end_at
):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $object_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT
          shift_id,
          object_id,
          shift_name,
          base_payment,
          deadline_at,
          start_at,
          opened_at,
          closed_at,
          status,
          created_at,
          updated_at
        FROM firm_shifts
        WHERE object_id = $object_id
          AND (
            (
              status IN ('pending', 'active')
              AND (start_at IS NULL OR start_at < $end_at)
            )
            OR
            (
              status IN ('cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND (
                (closed_at IS NOT NULL AND closed_at >= $start_at AND closed_at < $end_at)
                OR
                (closed_at IS NULL AND updated_at >= $start_at AND updated_at < $end_at)
              )
            )
          );
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$object_id": object_id, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            shift_id = norm_str(getattr(row, "shift_id", None))
            if not shift_id:
                continue
            result.append(
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
    return result


def fetch_object_deals_for_day(
    *, objects_pool, objects_database, object_id, start_at, end_at
):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{objects_database}');
        DECLARE $object_id AS Utf8;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT
          deal_id,
          object_id,
          deal_name,
          base_payment,
          deadline_at,
          start_at,
          status,
          created_at,
          updated_at
        FROM firm_deals
        WHERE object_id = $object_id
          AND (
            (
              status IN ('active')
              AND (start_at IS NULL OR start_at < $end_at)
            )
            OR
            (
              status IN ('archived', 'cancelled', 'completed', 'force_cancelled', 'force_completed', 'rejected')
              AND updated_at >= $start_at AND updated_at < $end_at
            )
          );
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$object_id": object_id, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            deal_id = norm_str(getattr(row, "deal_id", None))
            if not deal_id:
                continue
            result.append(
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
    return result


def fetch_assign_event_rows(*, events_pool, events_database, firm_id, end_at):
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $firm_id AS Utf8;
        DECLARE $end_at AS Timestamp;
        SELECT event_id, event_type, created_at, sequence_number
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
            result.append(
                {
                    "event_id": event_id,
                    "event_type": norm_str(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return result


def build_latest_assign_maps(
    *, assign_event_rows, states_by_event_id, shift_ids, deal_ids
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    latest_shift_by_id: Dict[str, Dict[str, Any]] = {}
    latest_deal_by_id: Dict[str, Dict[str, Any]] = {}
    shift_set = {norm_str(v) for v in shift_ids if norm_str(v)}
    deal_set = {norm_str(v) for v in deal_ids if norm_str(v)}

    for row in assign_event_rows:
        event_id = norm_str(row.get("event_id"))
        event_type = norm_str(row.get("event_type")).lower()
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        sequence_number = int(row.get("sequence_number") or 0)
        event_at = to_iso_utc(state.get("event_at")) or to_iso_utc(
            row.get("created_at")
        )
        if event_type == "shift_assign":
            shift_id = norm_str(state.get("shift_id"))
            if not shift_id or shift_id not in shift_set:
                continue
            current = latest_shift_by_id.get(shift_id)
            if current is None or sequence_number > int(
                current.get("sequence_number") or 0
            ):
                latest_shift_by_id[shift_id] = {
                    "shift_id": shift_id,
                    "worker_id": norm_str(state.get("worker_id")),
                    "object_id": norm_str(state.get("object_id")),
                    "event_id": event_id,
                    "event_at": event_at,
                    "sequence_number": sequence_number,
                }
        elif event_type == "deal_assign":
            deal_id = norm_str(state.get("deal_id"))
            if not deal_id or deal_id not in deal_set:
                continue
            current = latest_deal_by_id.get(deal_id)
            if current is None or sequence_number > int(
                current.get("sequence_number") or 0
            ):
                latest_deal_by_id[deal_id] = {
                    "deal_id": deal_id,
                    "worker_id": norm_str(state.get("worker_id")),
                    "object_id": norm_str(state.get("object_id")),
                    "event_id": event_id,
                    "event_at": event_at,
                    "sequence_number": sequence_number,
                }

    return latest_shift_by_id, latest_deal_by_id


def fetch_manual_presence_rows(
    *, events_pool, events_database, user_ids, start_at, end_at
):
    ids = norm_ids(user_ids)
    if not ids:
        return []
    result: List[Dict[str, Any]] = []

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{events_database}');
        DECLARE $user_ids AS List<Utf8>;
        DECLARE $start_at AS Timestamp;
        DECLARE $end_at AS Timestamp;
        SELECT user_id, event_id, event_type, created_at, sequence_number
        FROM user_events
        WHERE user_id IN $user_ids
          AND event_type IN ('{EVENT_TYPE_OBJ_ENTER}', '{EVENT_TYPE_OBJ_LEAVE}')
          AND created_at >= $start_at
          AND created_at < $end_at
        ORDER BY sequence_number ASC;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$user_ids": ids, "$start_at": start_at, "$end_at": end_at},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = norm_str(getattr(row, "event_id", None))
            if not event_id:
                continue
            result.append(
                {
                    "user_id": norm_str(getattr(row, "user_id", None)),
                    "event_id": event_id,
                    "event_type": norm_str(getattr(row, "event_type", None)).lower(),
                    "created_at": getattr(row, "created_at", None),
                    "sequence_number": getattr(row, "sequence_number", None),
                }
            )

    events_pool.retry_operation_sync(_tx)
    return result


def build_latest_manual_presence_by_user(
    *, manual_presence_rows, states_by_event_id, firm_id, object_id
):
    latest_by_user: Dict[str, Dict[str, Any]] = {}
    for row in manual_presence_rows:
        event_id = norm_str(row.get("event_id"))
        state = states_by_event_id.get(event_id)
        if not isinstance(state, dict):
            continue
        if norm_str(state.get("firm_id")) not in ("", firm_id):
            continue
        if norm_str(state.get("object_id")) != object_id:
            continue
        user_id = norm_str(extract_user_id(state) or row.get("user_id"))
        if not user_id:
            continue
        sequence_number = int(row.get("sequence_number") or 0)
        current = latest_by_user.get(user_id)
        if current is not None and sequence_number <= int(
            current.get("sequence_number") or 0
        ):
            continue
        latest_by_user[user_id] = {
            "event_id": event_id,
            "event_type": norm_str(row.get("event_type")).lower(),
            "event_at": to_iso_utc(state.get("event_at")) or to_iso_utc(
                row.get("created_at")
            ),
            "sequence_number": sequence_number,
        }
    return latest_by_user


def fetch_user_profiles_map(*, firms_pool, firms_database, user_ids):
    ids = norm_ids(user_ids)
    if not ids:
        return {}

    result_map = {}

    def _tx(session):
        q = f"""
        PRAGMA TablePathPrefix('{firms_database}');
        DECLARE $user_ids AS List<Utf8>;
        SELECT user_id, full_name, email, phone_number, tags_json
        FROM UserProfiles
        WHERE user_id IN $user_ids;
        """
        rs = session.transaction().execute(
            session.prepare(q),
            {"$user_ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            user_id = str(getattr(row, "user_id", "") or "").strip()
            if not user_id:
                continue
            tags_val = safe_json(getattr(row, "tags_json", None))
            if not isinstance(tags_val, list):
                tags_val = []
            result_map[user_id] = {
                "user_id": user_id,
                "full_name": getattr(row, "full_name", None),
                "email": getattr(row, "email", None),
                "phone_number": getattr(row, "phone_number", None),
                "tags_json": tags_val,
            }

    firms_pool.retry_operation_sync(_tx)
    return result_map


def fetch_worker_percents_map(*, firms_pool, firms_database, firm_id):
    query_attributions = f"""
    SELECT worker_user_id, percent_snapshot
    FROM dispatcher_attributions
    WHERE firm_id = '{firm_id}'
    ORDER BY
        CASE
            WHEN attribution_type = 'dispatcher' THEN 0
            WHEN attribution_type = 'nominal' THEN 1
            ELSE 2
        END ASC,
        updated_at DESC,
        created_at DESC;
    """

    attributions_result = None

    def _read_attributions(session):
        nonlocal attributions_result
        attributions_result = session.transaction().execute(
            query_attributions, commit_tx=True
        )

    firms_pool.retry_operation_sync(_read_attributions)

    worker_percents = {}
    if attributions_result and attributions_result[0].rows:
        for row in attributions_result[0].rows:
            worker_id = str(row.worker_user_id)
            if worker_id in worker_percents:
                continue
            worker_percents[worker_id] = row.percent_snapshot
    return worker_percents
