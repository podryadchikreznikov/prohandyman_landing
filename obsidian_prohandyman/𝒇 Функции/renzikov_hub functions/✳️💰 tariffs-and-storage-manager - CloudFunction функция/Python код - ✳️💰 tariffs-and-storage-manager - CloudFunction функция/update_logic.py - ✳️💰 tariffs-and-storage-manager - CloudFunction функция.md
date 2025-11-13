
```python
import json
import ydb  # ИСПРАВЛЕНО: Добавлен недостающий импорт
from utils import JsonLogger, ok, loads_safe, now_utc
from custom_errors import LogicError, NotFoundError

VALID_JSON_FIELDS = {"subscription_info_json", "storage_info_json", "confidential_data_json"}

def update_json_fields(session, firm_id, target_json_field, updates):
    logger = JsonLogger()
    logger.info("tariffs.update_json_fields", firm_id=firm_id, target=target_json_field)
    if not target_json_field or target_json_field not in VALID_JSON_FIELDS:
        raise LogicError(f"Invalid 'target_json_field'. Must be one of {VALID_JSON_FIELDS}")
    if not isinstance(updates, dict):
        raise LogicError("'updates' must be a JSON object.")

    tx = session.transaction(ydb.SerializableReadWrite())
    
    logger.info("tariffs.read_record")
    read_query = session.prepare(f"DECLARE $firm_id AS Utf8; SELECT {target_json_field} FROM `tariffs_and_storage` WHERE firm_id = $firm_id;")
    res = tx.execute(read_query, {"$firm_id": firm_id})
    if not res[0].rows:
        raise NotFoundError(f"Record for firm_id {firm_id} not found. Cannot update.")
    
    current_json_str = res[0].rows[0][target_json_field]
    current_data = loads_safe(current_json_str, default={})
    logger.info("tariffs.current_data", size=len(json.dumps(current_data)))
    
    logger.info("tariffs.apply_updates")
    current_data.update(updates)
    new_json_str = json.dumps(current_data)
    logger.info("tariffs.new_data", size=len(new_json_str))
    
    logger.info("tariffs.write_record")
    now = now_utc()
    update_query = session.prepare(f"""
        DECLARE $firm_id AS Utf8;
        DECLARE $new_json AS Json;
        DECLARE $now AS Timestamp;
        UPDATE `tariffs_and_storage` SET {target_json_field} = $new_json, updated_at = $now WHERE firm_id = $firm_id;
    """)
    tx.execute(update_query, {"$firm_id": firm_id, "$new_json": new_json_str, "$now": now})
    
    tx.commit()
    logger.info("tariffs.update_ok", firm_id=firm_id, target=target_json_field)
    return ok({"message": f"Field '{target_json_field}' updated successfully."})

def clear_json_fields(session, firm_id, fields_to_clear):
    logger = JsonLogger()
    logger.info("tariffs.clear_fields", firm_id=firm_id, fields=fields_to_clear)
    if not isinstance(fields_to_clear, list):
        raise LogicError("'fields_to_clear' must be a list of field names.")
    
    set_clauses = []
    for field in fields_to_clear:
        if field in VALID_JSON_FIELDS:
            set_clauses.append(f"{field} = CAST('{{}}' AS Json)")
        else:
            logger.warn("tariffs.clear_fields_invalid", field=field)
            
    if not set_clauses:
        raise LogicError("No valid fields provided to clear.")

    tx = session.transaction(ydb.SerializableReadWrite())
    now = now_utc()
    
    update_query_text = f"""
        DECLARE $firm_id AS Utf8;
        DECLARE $now AS Timestamp;
        UPDATE `tariffs_and_storage` SET {', '.join(set_clauses)}, updated_at = $now WHERE firm_id = $firm_id;
    """
    tx.execute(session.prepare(update_query_text), {"$firm_id": firm_id, "$now": now})
    
    tx.commit()
    logger.info("tariffs.clear_fields_ok", firm_id=firm_id)
    return ok({"message": f"Fields {fields_to_clear} cleared successfully."})
```