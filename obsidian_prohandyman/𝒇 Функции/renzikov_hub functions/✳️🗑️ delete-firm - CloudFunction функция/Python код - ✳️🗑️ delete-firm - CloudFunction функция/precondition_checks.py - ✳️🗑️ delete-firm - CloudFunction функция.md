```python
import json
import logging
import ydb
from custom_errors import AuthError, PreconditionFailedError

def _check_owner_permissions(session, user_id, firm_id):
    """Проверяет, что пользователь является владельцем фирмы."""
    logging.info("Checking owner permissions...")
    query = session.prepare("DECLARE $uid AS Utf8; DECLARE $fid AS Utf8; SELECT roles FROM Users WHERE user_id = $uid AND firm_id = $fid;")
    res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$uid": user_id, "$fid": firm_id}, commit_tx=True)
    
    if not res[0].rows:
        raise AuthError("User is not a member of the specified firm.")
    
    roles = json.loads(res[0].rows[0].roles or '[]')
    if roles != ["OWNER"]:
        raise AuthError("Access denied. Only the firm owner can perform this operation.")
    logging.info("Owner permissions confirmed.")

def _check_integrations(session, firm_id):
    """Проверяет, что нет активных интеграций."""
    logging.info("Checking for active integrations...")
    query = session.prepare("DECLARE $fid AS Utf8; SELECT integrations_json FROM Firms WHERE firm_id = $fid;")
    res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$fid": firm_id}, commit_tx=True)
    
    if not res[0].rows: return # Фирма уже удалена, проверка пройдена
    
    integrations = json.loads(res[0].rows[0].integrations_json or '{}')
    for name, details in integrations.items():
        if isinstance(details, dict) and details.get("enabled") is True:
            raise PreconditionFailedError(f"Cannot delete firm: active integration '{name}' found.")
    logging.info("No active integrations found.")


def run_all_checks(pool, user_jwt, user_id, firm_id):
    """Запускает все проверки предусловий."""
    pool.retry_operation_sync(lambda s: _check_owner_permissions(s, user_id, firm_id))
    pool.retry_operation_sync(lambda s: _check_integrations(s, firm_id))
    logging.info("All precondition checks completed (tasks/clients checks skipped - not in current project).")
```