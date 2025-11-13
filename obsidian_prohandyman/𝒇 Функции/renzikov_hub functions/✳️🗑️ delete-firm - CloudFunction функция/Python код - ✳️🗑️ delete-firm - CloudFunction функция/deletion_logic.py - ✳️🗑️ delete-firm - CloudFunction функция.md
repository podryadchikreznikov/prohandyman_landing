```python
import logging
import os
import ydb
import invoke_utils

def _delete_all_employees(user_jwt, firm_id, owner_id):
    """Удаляет всех сотрудников, кроме владельца."""
    logging.info("Starting deletion of all employees...")
    employees_response = invoke_utils.invoke_function(
        invoke_utils.FUNCTION_ID_EMPLOYEE_MANAGER,
        {"firm_id": firm_id},
        user_jwt
    )
    if not employees_response or not employees_response.get('data'):
        logging.warning("Could not retrieve employee list.")
        return

    employees_to_delete = [emp for emp in employees_response['data'] if emp.get('user_id') and emp['user_id'] != owner_id]
    if not employees_to_delete:
        logging.info("No other employees found to delete.")
        return
    
    logging.info(f"Found {len(employees_to_delete)} employees to delete.")
    for i, emp in enumerate(employees_to_delete):
        invoke_utils.invoke_function(
            invoke_utils.FUNCTION_ID_EMPLOYEE_MANAGER,
            {"firm_id": firm_id, "user_id_to_delete": emp['user_id']},
            user_jwt
        )
        logging.info(f"  - Deleted employee {i+1}/{len(employees_to_delete)} ({emp['user_id']})")
    logging.info("All employees deleted.")


def _delete_tariffs_and_storage_record(firm_id):
    """Удаляет запись о тарифах и хранилище фирмы."""
    logging.info("Starting deletion of tariffs and storage record...")
    try:
        from utils import get_driver
        tariffs_driver = get_driver(invoke_utils.YDB_ENDPOINT_TARIFFS_AND_STORAGE, invoke_utils.YDB_DATABASE_TARIFFS_AND_STORAGE)
        tariffs_pool = ydb.SessionPool(tariffs_driver)
        
        def delete_record(session):
            query = session.prepare("DECLARE $fid AS Utf8; DELETE FROM tariffs_and_storage WHERE firm_id = $fid;")
            session.transaction(ydb.SerializableReadWrite()).execute(query, {"$fid": firm_id}, commit_tx=True)
        
        tariffs_pool.retry_operation_sync(delete_record)
        logging.info("Tariffs and storage record deleted successfully.")
    except Exception as e:
        logging.error(f"Failed to delete tariffs and storage record: {e}")
        # Не прерываем процесс удаления, так как это не критично

def _delete_firm_records(session, firm_id, owner_id):
    """Удаляет финальные записи о фирме и владении."""
    logging.info("Starting final cleanup of Firms and Users tables...")
    tx = session.transaction(ydb.SerializableReadWrite())
    
    # Удаляем запись о фирме
    tx.execute(session.prepare("DECLARE $fid AS Utf8; DELETE FROM Firms WHERE firm_id = $fid;"), {"$fid": firm_id})
    # Удаляем запись о владении
    tx.execute(session.prepare("DECLARE $uid AS Utf8; DECLARE $fid AS Utf8; DELETE FROM Users WHERE user_id = $uid AND firm_id = $fid;"), {"$uid": owner_id, "$fid": firm_id})
    
    tx.commit()
    logging.info("Final records from Firms and Users tables deleted.")

def run_all_deletions(pool, user_jwt, owner_id, firm_id):
    """Запускает все шаги по удалению."""
    logging.info("Skipping tasks/clients deletion - not in current project.")
    _delete_all_employees(user_jwt, firm_id, owner_id)
    _delete_tariffs_and_storage_record(firm_id)
    pool.retry_operation_sync(lambda s: _delete_firm_records(s, firm_id, owner_id))
```