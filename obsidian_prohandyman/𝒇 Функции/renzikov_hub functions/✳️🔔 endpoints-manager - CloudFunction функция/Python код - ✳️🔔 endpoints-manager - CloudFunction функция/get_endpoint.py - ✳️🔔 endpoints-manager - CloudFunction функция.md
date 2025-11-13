
```python
# get_endpoint.py

import json
import ydb
from utils import JsonLogger, ok, loads_safe

def handle_get_endpoints(pool, user_id):
    logger = JsonLogger()
    logger.info("endpoints.get_list", user_id=user_id)
    
    def get_list(session):
        query = session.prepare("""
            DECLARE $uid AS Utf8;
            SELECT 
                platform,
                push_token,
                endpoint_arn,
                is_enabled,
                device_info_json,
                created_at,
                updated_at
            FROM UserEndpoints VIEW user_id_index WHERE user_id = $uid;
        """)
        res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$uid": user_id}, commit_tx=True)
        
        data = []
        for row in res[0].rows:
            item = {c.name: row[c.name] for c in res[0].columns}
            if 'device_info_json' in item:
                item['device_info_json'] = loads_safe(item.get('device_info_json'), default={})
            data.append(item)
        return data

    result_data = pool.retry_operation_sync(get_list)
    return ok({"data": result_data})
```