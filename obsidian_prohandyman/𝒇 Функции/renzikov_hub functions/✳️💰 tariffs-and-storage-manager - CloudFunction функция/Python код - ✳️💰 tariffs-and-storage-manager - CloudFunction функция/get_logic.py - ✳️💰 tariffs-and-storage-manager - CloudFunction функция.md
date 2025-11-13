
```python
import json
import ydb  # ИСПРАВЛЕНО: Добавлен недостающий импорт
from utils import ok, loads_safe, now_utc, JsonLogger
from custom_errors import NotFoundError

DEFAULT_QUOTA_BYTES = 100 * 1024 * 1024 # 100 MB

def _create_default_record(session, firm_id):
    logger = JsonLogger()
    logger.info("tariffs.create_default", firm_id=firm_id)
    now = now_utc()
    default_subscription = {"plan_id": "free", "started_at": now.isoformat(), "expires_at": None, "auto_renew": False, "status": "active", "quota_bytes": DEFAULT_QUOTA_BYTES}
    default_storage = {"used_bytes": 0, "last_recalculated_at": now.isoformat()}
    
    query_text = """
        DECLARE $firm_id AS Utf8;
        DECLARE $sub_info AS Json;
        DECLARE $storage_info AS Json;
        DECLARE $conf_data AS Json;
        DECLARE $created_at AS Timestamp;
        DECLARE $updated_at AS Timestamp;
        UPSERT INTO `tariffs_and_storage` (firm_id, subscription_info_json, storage_info_json, confidential_data_json, created_at, updated_at)
        VALUES ($firm_id, $sub_info, $storage_info, $conf_data, $created_at, $updated_at);
    """
    params = {
        "$firm_id": firm_id,
        "$sub_info": json.dumps(default_subscription),
        "$storage_info": json.dumps(default_storage),
        "$conf_data": json.dumps({}),
        "$created_at": now,
        "$updated_at": now
    }
    try:
        session.transaction(ydb.SerializableReadWrite()).execute(session.prepare(query_text), params, commit_tx=True)
        logger.info("tariffs.create_default_ok", firm_id=firm_id)
    except Exception as e:
        logger.error("tariffs.create_default_failed", firm_id=firm_id, error=str(e))
        raise
    
    return {
        "firm_id": firm_id,
        "subscription_info_json": default_subscription,
        "storage_info_json": default_storage,
        "confidential_data_json": {},
        "created_at": now,
        "updated_at": now
    }

def get_or_create_record(session, firm_id):
    logger = JsonLogger()
    logger.info("tariffs.get_or_create", firm_id=firm_id)
    query = session.prepare("DECLARE $firm_id AS Utf8; SELECT * FROM `tariffs_and_storage` WHERE firm_id = $firm_id;")
    res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$firm_id": firm_id}, commit_tx=True)

    if res[0].rows:
        row = res[0].rows[0]
        data = {}
        for c in res[0].columns:
            value = row[c.name]
            if 'json' in c.name:
                data[c.name] = loads_safe(value, default={})
            else:
                data[c.name] = value
    else:
        data = _create_default_record(session, firm_id)
    return ok({"data": data})
```