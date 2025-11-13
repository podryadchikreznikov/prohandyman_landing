```python
import json
import ydb
from custom_errors import LogicError, NotFoundError
from utils import JsonLogger, ok

def archive_notice(session, table_name, notice_id):
    logger = JsonLogger()
    if not notice_id:
        logger.warn("archive_missing_notice_id", table=table_name)
        raise LogicError("notice_id is required for ARCHIVE action.")
    
    tx = session.transaction(ydb.SerializableReadWrite())

    check_query = session.prepare(f"DECLARE $id AS Utf8; SELECT 1 FROM `{table_name}` WHERE notice_id = $id;")
    logger.info("yql_check_existence", notice_id=notice_id, table=table_name)
    check_res = tx.execute(check_query, {"$id": notice_id})
    if not check_res[0].rows:
        logger.warn("notice_not_found_for_archive", notice_id=notice_id, table=table_name)
        raise NotFoundError(f"Notice with id {notice_id} not found.")

    update_query = session.prepare(f"UPDATE `{table_name}` SET is_archived = true WHERE notice_id = $id;")
    logger.info("yql_update_archive", notice_id=notice_id, table=table_name)
    tx.execute(update_query, {"$id": notice_id})
    
    tx.commit()
    logger.info("notice_archived", notice_id=notice_id, table=table_name)
    
    return ok({"message": "Notice archived successfully."})
```