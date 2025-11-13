
```python
# storage_logic.py

import os
import re
import json
import ydb
from utils import storage_utils, JsonLogger, ok, loads_safe, now_utc
from custom_errors import LogicError, QuotaExceededError, NotFoundError, AuthError
import get_logic

def handle_get_upload_url(pool, firm_id, filename, filesize):
    logger = JsonLogger()
    logger.info("storage.get_upload_url", firm_id=firm_id, filename=filename, filesize=filesize)
    if not all([filename, filesize]):
        raise LogicError("filename and filesize are required for GET_UPLOAD_URL.")
    if not isinstance(filesize, int) or filesize <= 0:
        raise LogicError("filesize must be a positive integer.")

    # Шаг 1: Получаем актуальный размер использованного пространства из Object Storage
    logger.info("storage.calc_usage_s3")
    s3_client = storage_utils.get_s3_client()
    bucket_name = os.environ['STORAGE_BUCKET_NAME']
    try:
        prefix = f"{firm_id}/"
        actual_used_bytes = storage_utils.get_folder_size(s3_client, bucket_name, prefix)
    except Exception:
        logger.error("storage.calc_usage_failed", firm_id=firm_id)
        raise Exception("Could not verify storage quota due to an internal error.")

    # Шаг 2: Получаем запись из БД, чтобы узнать квоту и сравнить с актуальным использованием
    logger.info("storage.fetch_record")
    record_response = pool.retry_operation_sync(lambda s: get_logic.get_or_create_record(s, firm_id))
    record_data = loads_safe((record_response or {}).get('body'), default={}).get('data', {})
    
    quota_bytes = record_data.get('subscription_info_json', {}).get('quota_bytes', 0)
    used_bytes_from_db = record_data.get('storage_info_json', {}).get('used_bytes', 0)
    
    logger.info("storage.quota_check", firm_id=firm_id, actual_used=actual_used_bytes, file_size=filesize, quota=quota_bytes)

    # Шаг 3: Проверяем квоту, используя актуальные данные
    if (actual_used_bytes + filesize) > quota_bytes:
        raise QuotaExceededError(f"Upload failed: storage quota will be exceeded. Used: {actual_used_bytes}, File: {filesize}, Quota: {quota_bytes}")

    # Шаг 4: (Опционально, но рекомендуется) Если данные в БД устарели, синхронизируем их
    if actual_used_bytes != used_bytes_from_db:
        logger.warn("storage.usage_out_of_sync", firm_id=firm_id, db_used=used_bytes_from_db, real_used=actual_used_bytes)
        def sync_transaction(session):
            storage_info = record_data.get('storage_info_json', {})
            storage_info['used_bytes'] = actual_used_bytes
            storage_info['last_recalculated_at'] = now_utc().isoformat()
            
            update_q = session.prepare("DECLARE $fid AS Utf8; DECLARE $sij AS Json; UPDATE `tariffs_and_storage` SET storage_info_json = $sij WHERE firm_id = $fid;")
            tx = session.transaction(ydb.SerializableReadWrite())
            tx.execute(update_q, {"$fid": firm_id, "$sij": json.dumps(storage_info)})
            logger.info("storage.sync_ok", firm_id=firm_id, used_bytes=actual_used_bytes)
        
        pool.retry_operation_sync(sync_transaction)

    # Шаг 5: Если проверка квоты пройдена, генерируем ссылку для загрузки
    logger.info("storage.generate_upload_url")
    file_key, upload_url = storage_utils.generate_upload_artefacts(firm_id, filename)

    if not upload_url or not file_key:
        logger.error("storage.generate_upload_url_failed")
        raise Exception("Could not generate an upload URL from the storage service.")

    logger.info("storage.generate_upload_url_ok", file_key=file_key)
    return ok({"upload_url": upload_url, "file_key": file_key})


def handle_delete_file(pool, firm_id, file_key):
    logger = JsonLogger()
    logger.info("storage.delete_file", firm_id=firm_id, file_key=file_key)
    if not file_key:
        raise LogicError("file_key is required for DELETE action.")
    if not file_key.startswith(f"{firm_id}/"):
        raise AuthError("Permission denied: you are not allowed to access this file key.")

    s3_client = storage_utils.get_s3_client()
    bucket_name = os.environ['STORAGE_BUCKET_NAME']
    
    try:
        logger.info("storage.head_object", file_key=file_key)
        head_response = s3_client.head_object(Bucket=bucket_name, Key=file_key)
        file_size = head_response['ContentLength']
        logger.info("storage.head_ok", size=file_size)
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.warn("storage.not_found", file_key=file_key)
            raise NotFoundError(f"File with key {file_key} not found.")
        else:
            logger.error("storage.head_error", error=str(e))
            raise

    logger.info("storage.delete_object", file_key=file_key)
    storage_utils.delete_object(s3_client, bucket_name, file_key)
    logger.info("storage.delete_ok", file_key=file_key)

    if file_size > 0:
        logger.info("storage.decrement_db", bytes=file_size)
        def decrement_storage_size_transaction(session):
            tx = session.transaction(ydb.SerializableReadWrite())
            read_q = session.prepare("DECLARE $fid AS Utf8; SELECT storage_info_json FROM `tariffs_and_storage` WHERE firm_id = $fid;")
            res = tx.execute(read_q, {"$fid": firm_id})
            if not res[0].rows:
                logger.warn("storage.decrement_db_missing", firm_id=firm_id)
                return

            storage_info = loads_safe(res[0].rows[0].storage_info_json, default={})
            current_used = storage_info.get('used_bytes', 0)
            logger.info("storage.decrement_db_calc", current_used=current_used, new_used=max(0, current_used - file_size))
            storage_info['used_bytes'] = max(0, current_used - file_size)
            
            update_q = session.prepare("DECLARE $fid AS Utf8; DECLARE $sij AS Json; UPDATE `tariffs_and_storage` SET storage_info_json = $sij WHERE firm_id = $fid;")
            tx.execute(update_q, {"$fid": firm_id, "$sij": json.dumps(storage_info)})
            tx.commit()
            logger.info("storage.decrement_db_ok", firm_id=firm_id)
        
        pool.retry_operation_sync(decrement_storage_size_transaction)

    return ok({"message": "File deleted successfully"})

def handle_get_download_url(firm_id, file_key):
    """
    Обрабатывает запрос на получение ссылки для скачивания.
    """
    logger = JsonLogger()
    logger.info("storage.get_download_url", firm_id=firm_id, file_key=file_key)
    if not file_key:
        raise LogicError("file_key is required for GET_DOWNLOAD_URL action.")
    
    if not file_key.startswith(f"{firm_id}/"):
        raise AuthError("Permission denied: you are not allowed to access this file key.")

    s3_client = storage_utils.get_s3_client()
    bucket_name = os.environ['STORAGE_BUCKET_NAME']

    try:
        s3_client.head_object(Bucket=bucket_name, Key=file_key)
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise NotFoundError(f"Cannot get download URL. File with key {file_key} not found.")
        else:
            raise

    download_url = storage_utils.generate_presigned_download_url(s3_client, bucket_name, file_key)

    if not download_url:
        raise Exception("Could not generate a download URL from the storage service.")

    logger.info("storage.get_download_url_ok", file_key=file_key)
    return ok({"download_url": download_url, "file_key": file_key})

def handle_confirm_upload(pool, firm_id, file_key):
    """
    Подтверждает успешную загрузку файла, получает его размер из S3
    и атомарно увеличивает счетчик used_bytes в базе данных.
    """
    logger = JsonLogger()
    logger.info("storage.confirm_upload", firm_id=firm_id, file_key=file_key)
    if not file_key:
        raise LogicError("file_key is required for CONFIRM_UPLOAD action.")
    if not file_key.startswith(f"{firm_id}/"):
        raise AuthError("Permission denied: you are not allowed to access this file key.")

    s3_client = storage_utils.get_s3_client()
    bucket_name = os.environ['STORAGE_BUCKET_NAME']
    
    file_size = 0
    try:
        logger.info("storage.head_object", file_key=file_key)
        file_size = s3_client.head_object(Bucket=bucket_name, Key=file_key)['ContentLength']
        logger.info("storage.head_ok", size=file_size)
    except s3_client.exceptions.ClientError as e:
        if e.response['Error']['Code'] == '404':
            raise NotFoundError(f"Cannot confirm upload. File with key {file_key} not found in storage.")
        else:
            raise

    if file_size > 0:
        logger.info("storage.increment_db", bytes=file_size)
        
        def increment_storage_size_transaction(session):
            tx = session.transaction(ydb.SerializableReadWrite())
            # Сначала читаем текущее значение
            read_q = session.prepare("DECLARE $fid AS Utf8; SELECT storage_info_json FROM `tariffs_and_storage` WHERE firm_id = $fid;")
            res = tx.execute(read_q, {"$fid": firm_id})
            if not res[0].rows:
                logger.warn("storage.increment_db_missing", firm_id=firm_id)
                return

            storage_info = loads_safe(res[0].rows[0].storage_info_json, default={})
            current_used = storage_info.get('used_bytes', 0)
            logger.info("storage.increment_db_calc", current_used=current_used, new_used=current_used + file_size)
            storage_info['used_bytes'] = current_used + file_size
            
            # Затем записываем новое
            update_q = session.prepare("DECLARE $fid AS Utf8; DECLARE $sij AS Json; UPDATE `tariffs_and_storage` SET storage_info_json = $sij WHERE firm_id = $fid;")
            tx.execute(update_q, {"$fid": firm_id, "$sij": json.dumps(storage_info)})
            tx.commit()
            logger.info("storage.increment_db_ok", firm_id=firm_id)
        
        pool.retry_operation_sync(increment_storage_size_transaction)

    return ok({"message": "Upload confirmed and storage usage updated."})
```