```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
import traceback
from typing import Optional, Tuple

import ydb

from utils import (
    parse_event, EventParseError,
    ok, bad_request, server_error,
    JsonLogger, now_utc, get_session_pool,
)

_SA_CREDENTIALS: Optional[ydb.iam.ServiceAccountCredentials] = None


def _get_sa_credentials() -> ydb.iam.ServiceAccountCredentials:
    """Materialize SA_KEY_JSON into a temp file once and reuse credentials."""
    global _SA_CREDENTIALS
    if _SA_CREDENTIALS:
        return _SA_CREDENTIALS

    payload = os.environ.get("SA_KEY_JSON")
    if not payload:
        raise RuntimeError("SA_KEY_JSON environment variable is required")

    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    target = os.path.join(tempfile.gettempdir(), f"sa-key-{digest}.json")
    if not os.path.isfile(target):
        with open(target, "w", encoding="utf-8") as fp:
            fp.write(payload)
    _SA_CREDENTIALS = ydb.iam.ServiceAccountCredentials.from_file(target)
    return _SA_CREDENTIALS


def _build_pool(endpoint_var: str, database_var: str) -> Tuple[ydb.SessionPool, str]:
    endpoint = os.environ.get(endpoint_var)
    database = os.environ.get(database_var)
    if not endpoint or not database:
        raise RuntimeError(f"{endpoint_var}/{database_var} are required")
    creds = _get_sa_credentials()
    pool = get_session_pool(endpoint, database, credentials=creds)
    return pool, database


def _validate_uuid(uid: str) -> bool:
    try:
        uuid.UUID(uid)
        return True
    except Exception:
        return False


def _format_sequence_number(num: int) -> str:
    return str(num)


def handler(event, context):
    # parse event and init logger
    try:
        req = parse_event(event)
    except EventParseError as e:
        return bad_request(str(e))

    headers = req.get("headers") or {}
    corr_id = headers.get("x-correlation-id") or headers.get("x-correlationid") or None
    logger = JsonLogger(correlation_id=corr_id)

    body = req.get("body_dict") or {}
    entity_type = body.get("entity_type")
    uid = body.get("uuid")

    if not entity_type or not isinstance(entity_type, str):
        return bad_request("entity_type is required and must be string")
    if not uid or not isinstance(uid, str):
        return bad_request("uuid is required and must be string")
    if not _validate_uuid(uid):
        return bad_request("uuid must be valid UUID format")

    # connect to YDB using metadata-system endpoint
    try:
        pool, database = _build_pool("YDB_ENDPOINT_META", "YDB_DATABASE_META")
    except Exception as e:
        logger.error("db.connect_error", error=str(e))
        return server_error("Database connection error")

    def tx_body(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())

        # check existing aggregate
        check_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $entity_type AS Utf8;
            DECLARE $uuid AS Utf8;
            SELECT last_seq_no FROM aggregate_state WHERE entity_type = $entity_type AND uuid = $uuid;
        """
        params = {"$entity_type": entity_type, "$uuid": uid}
        rs = tx.execute(session.prepare(check_q), params)
        if rs and rs[0].rows:
            existing = str(getattr(rs[0].rows[0], "last_seq_no", ""))
            tx.rollback()
            return {"status": "EXISTING", "entity_type": entity_type, "uuid": uid, "sequence_number": existing}

        # try counter table first (recommended)
        try:
            seq_name = "global"
            sel_counter_q = f"""
                PRAGMA TablePathPrefix('{database}');
                DECLARE $name AS Utf8;
                SELECT value FROM sequence_counters WHERE seq_name = $name;
            """
            rs2 = tx.execute(session.prepare(sel_counter_q), {"$name": seq_name})
            if rs2 and rs2[0].rows:
                cur = int(getattr(rs2[0].rows[0], "value", 0))
                new_val = cur + 1
                upd_q = f"""
                    PRAGMA TablePathPrefix('{database}');
                    DECLARE $name AS Utf8;
                    DECLARE $value AS Uint64;
                    UPDATE sequence_counters SET value = $value WHERE seq_name = $name;
                """
                tx.execute(session.prepare(upd_q), {"$name": seq_name, "$value": new_val})
            else:
                new_val = 1
                ins_q = f"""
                    PRAGMA TablePathPrefix('{database}');
                    DECLARE $name AS Utf8;
                    DECLARE $value AS Uint64;
                    INSERT INTO sequence_counters (seq_name, value) VALUES ($name, $value);
                """
                tx.execute(session.prepare(ins_q), {"$name": seq_name, "$value": new_val})
        except Exception as e:
            # fallback to MAX(last_seq_no)
            logger.warning("counter_table_missing_or_error", error=str(e))
            max_q = f"""
                PRAGMA TablePathPrefix('{database}');
                SELECT MAX(last_seq_no) AS max_no FROM aggregate_state;
            """
            max_rs = tx.execute(session.prepare(max_q), {})
            max_number = 0
            if max_rs and max_rs[0].rows and getattr(max_rs[0].rows[0], "max_no", None):
                try:
                    max_number = int(str(getattr(max_rs[0].rows[0], "max_no")))
                except Exception:
                    max_number = 0
            new_val = max_number + 1

        new_str = _format_sequence_number(new_val)

        insert_q = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $entity_type AS Utf8;
            DECLARE $uuid AS Utf8;
            DECLARE $last_seq_no AS Utf8;
            DECLARE $updated_at AS Timestamp;
            INSERT INTO aggregate_state (entity_type, uuid, last_seq_no, updated_at)
            VALUES ($entity_type, $uuid, $last_seq_no, $updated_at);
        """
        tx.execute(session.prepare(insert_q), {"$entity_type": entity_type, "$uuid": uid, "$last_seq_no": new_str, "$updated_at": now_utc()})
        tx.commit()
        return {"status": "NEW", "entity_type": entity_type, "uuid": uid, "sequence_number": new_str}

    try:
        result = pool.retry_operation_sync(tx_body)
    except Exception as e:
        logger.error("tx.error", error=str(e), trace=traceback.format_exc())
        return server_error("Transaction error")

    return ok(result)
```
