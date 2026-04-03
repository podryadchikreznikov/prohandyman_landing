# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

import ydb

from utils.util_metadata import parse_json_value


def chunked(values: List[str], chunk_size: int) -> Iterable[List[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    for i in range(0, len(values), chunk_size):
        yield values[i : i + chunk_size]


def extract_user_id(state: Any) -> Optional[str]:
    if not isinstance(state, dict):
        return None
    for key in ("user_id", "worker_user_id", "worker_id", "employee_id"):
        v = state.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def extract_amount_kopeks(state: Any) -> Optional[int]:
    if not isinstance(state, dict):
        return None
    for key in (
        "amount_kopeks",
        "withhold_amount_kopeks",
        "withheld_kopeks",
        "withholding_kopeks",
    ):
        v = state.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, float) and v.is_integer():
            return int(v)
        if isinstance(v, str) and v.strip().isdigit():
            try:
                return int(v.strip())
            except Exception:
                continue
    return None


def fetch_firm_event_states(
    *,
    meta_pool: ydb.SessionPool,
    meta_database: str,
    firm_id: str,
    event_ids: List[str],
    logger,
    chunk_size: int = 200,
) -> Dict[str, dict]:
    """Fetch state_json for event_ids from aggregate_state_{firm_id}.

    Returns mapping: event_id -> state_json (dict).
    """
    if not event_ids:
        return {}

    out: Dict[str, dict] = {}

    def _read_chunk(session: ydb.Session, ids: List[str]) -> None:
        query = f"""
        PRAGMA TablePathPrefix('{meta_database}');
        DECLARE $ids AS List<Utf8>;
        SELECT entity_id, state_json
        FROM `aggregate_state_{firm_id}`
        WHERE entity_id IN $ids;
        """
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(query),
            {"$ids": ids},
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            event_id = str(getattr(row, "entity_id", "") or "").strip()
            if not event_id:
                continue
            raw_state = getattr(row, "state_json", None)
            parsed = parse_json_value(raw_state)
            if isinstance(parsed, dict):
                out[event_id] = parsed

    for ids in chunked(event_ids, chunk_size):
        try:
            meta_pool.retry_operation_sync(lambda s, _ids=ids: _read_chunk(s, _ids))
        except Exception as e:
            logger.error("analytics_getter.meta.fetch_state_failed", error=str(e))
            raise

    return out