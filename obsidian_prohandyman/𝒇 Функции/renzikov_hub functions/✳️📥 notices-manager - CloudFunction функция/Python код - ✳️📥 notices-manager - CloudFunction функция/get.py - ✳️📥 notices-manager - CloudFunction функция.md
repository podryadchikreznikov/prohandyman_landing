```python
import json
import math
import ydb
from custom_errors import NotFoundError
from utils import JsonLogger, ok, loads_safe
 
PAGE_SIZE = 100
 
def _format_notice(row, columns):
    data = {}
    for c in columns:
        value = row[c.name]
        if 'json' in c.name and value:
            data[c.name] = loads_safe(value, default=None)
        else:
            data[c.name] = value
    return data
 
def get_notices(session, table_name, notice_id=None, page=0, get_archived=False):
    logger = JsonLogger()
    try:
        tx = session.transaction(ydb.SerializableReadWrite())
 
        if notice_id:
            query = session.prepare(f"DECLARE $id AS Utf8; SELECT * FROM `{table_name}` WHERE notice_id = $id;")
            logger.info("yql_single_fetch", notice_id=notice_id, table=table_name)
            res = tx.execute(query, {"$id": notice_id})
            if not res[0].rows:
                logger.warn("notice_not_found", notice_id=notice_id, table=table_name)
                raise NotFoundError(f"Notice with id {notice_id} not found.")
            
            data = _format_notice(res[0].rows[0], res[0].columns)
            tx.commit()
            logger.info("fetched_single_notice", notice_id=notice_id, table=table_name)
            return ok({"data": data})
 
        page = int(page or 0)
        if page < 0:
            page = 0
        offset = page * PAGE_SIZE
 
        where_clause = "WHERE (is_archived IS NULL OR is_archived = false)"
        if get_archived:
            where_clause = "WHERE is_archived = true"
 
        count_query = session.prepare(f"SELECT COUNT(notice_id) AS total FROM `{table_name}` {where_clause};")
        logger.info("yql_count_query", clause=where_clause, table=table_name)
        count_res = tx.execute(count_query)
        total_items = count_res[0].rows[0].total if count_res[0].rows else 0
        total_pages = math.ceil(total_items / PAGE_SIZE) if total_items > 0 else 0
        
        logger.info("count_result", total=total_items, pages=total_pages, table=table_name)
 
        if total_items == 0:
            tx.commit()
            return ok({"metadata": {"total": 0, "page": 0, "pages": 0}, "data": []})
 
        if page >= total_pages and total_pages > 0:
            logger.warn("page_not_exist", page=page, total_pages=total_pages, table=table_name)
            raise NotFoundError(f"Page {page} does not exist. Total pages: {total_pages}.")
 
        select_data_query = session.prepare(f"SELECT * FROM `{table_name}` {where_clause} ORDER BY created_at DESC LIMIT {PAGE_SIZE} OFFSET {offset};")
        logger.info("yql_select_data", table=table_name, page=page, offset=offset)
        data_res = tx.execute(select_data_query)
        
        data = [_format_notice(row, data_res[0].columns) for row in data_res[0].rows]
        metadata = {"total": total_items, "page": page, "pages": total_pages}
        
        logger.info("fetched_notices", count=len(data), table=table_name, page=page)
        tx.commit()
        return ok({"metadata": metadata, "data": data})
 
    except ydb.SchemeError:
        logger.info("table_not_found", table=table_name)
        return ok({"metadata": {"total": 0, "page": 0, "pages": 0}, "data": []})
```
```