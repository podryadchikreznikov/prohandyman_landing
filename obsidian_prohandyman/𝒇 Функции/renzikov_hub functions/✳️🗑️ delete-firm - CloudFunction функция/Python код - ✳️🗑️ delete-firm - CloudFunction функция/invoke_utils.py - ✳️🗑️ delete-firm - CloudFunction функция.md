```python
import os
import json
import logging
import time
import ydb.iam
from utils import invoke_function as cloud_invoke_function

# Переменные окружения для YDB
YDB_ENDPOINT_TARIFFS_AND_STORAGE = os.environ.get("YDB_ENDPOINT_TARIFFS_AND_STORAGE")
YDB_DATABASE_TARIFFS_AND_STORAGE = os.environ.get("YDB_DATABASE_TARIFFS_AND_STORAGE")

# ID целевой функции employee-manager
FUNCTION_ID_EMPLOYEE_MANAGER = os.environ.get("FUNCTION_ID_EMPLOYEE_MANAGER")

# Кеш для IAM-токена
_IAM_TOKEN_CACHE = {"token": None, "expires_at": 0}

def _get_iam_token():
    """Получает и кеширует IAM-токен."""
    now = time.time()
    if _IAM_TOKEN_CACHE["token"] and now < _IAM_TOKEN_CACHE["expires_at"]:
        return _IAM_TOKEN_CACHE["token"]
    
    try:
        creds = ydb.iam.MetadataUrlCredentials()
        token, expires_at = creds.token
        _IAM_TOKEN_CACHE["token"] = token
        _IAM_TOKEN_CACHE["expires_at"] = expires_at - 60 # Запас в 60 секунд
        return token
    except Exception as e:
        logging.error(f"Failed to get IAM token: {e}", exc_info=True)
        return None

def invoke_function(function_id: str, payload: dict, user_jwt: str) -> dict | None:
    """Вызывает облачную функцию с авторизацией."""
    if not function_id:
        logging.error(f"Function ID is not specified for payload: {payload}")
        return None

    iam_token = _get_iam_token()
    if not iam_token:
        logging.error("Cannot invoke function, failed to get IAM token.")
        return None

    function_url = f"https://functions.yandexcloud.net/{function_id}"
    resp = cloud_invoke_function(
        function_url,
        method="POST",
        json_payload=payload,
        auth_headers={"Authorization": f"Bearer {iam_token}"},
        forward_headers={"X-Forwarded-Authorization": f"Bearer {user_jwt}"},
        timeout_s=20,
        retries=2,
        allow_hosts=("functions.yandexcloud.net",),
        parse_json=True,
    )
    if resp and resp.get("ok"):
        return resp.get("json") or {}
    logging.error(f"Error invoking function {function_id}: {resp and resp.get('error')}")
    return None


```