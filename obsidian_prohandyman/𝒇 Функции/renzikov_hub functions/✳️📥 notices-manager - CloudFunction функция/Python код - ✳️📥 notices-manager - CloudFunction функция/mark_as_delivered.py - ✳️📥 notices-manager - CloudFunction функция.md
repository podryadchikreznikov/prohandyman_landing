```python
import ydb
from custom_errors import LogicError
from utils import JsonLogger, ok, now_utc

def mark_notices_as_delivered(session, table_name, notice_ids):
    logger = JsonLogger()
    if not isinstance(notice_ids, list) or not notice_ids:
        logger.warn("invalid_notice_ids", table=table_name)
        raise LogicError("notice_ids must be a non-empty list.")
    
    tx = session.transaction(ydb.SerializableReadWrite())

    update_query = session.prepare(
        f"DECLARE $ids AS List<Utf8>; DECLARE $now AS Timestamp; UPDATE `{table_name}` SET is_delivered = true, delivered_at = $now WHERE notice_id IN $ids;"
    )
    logger.info("yql_update_mark_delivered", count=len(notice_ids), table=table_name)
    tx.execute(update_query, {
        "$ids": notice_ids,
        "$now": now_utc()
    })
    
    tx.commit()
    logger.info("marked_as_delivered", count=len(notice_ids), table=table_name)
    
    return ok({"message": f"{len(notice_ids)} notices marked as delivered."})
```