util_invoke

HTTP вызовы других функций/сервисов с retry логикой и защитой.

invoke.py

invoke_function(target, method="POST", json_payload=None, data_bytes=None, headers=None, auth_headers=None, forward_bearer=None, forward_headers=None, timeout_s=20, retries=2, backoff_base_s=0.5, allow_hosts=None, parse_json=True, max_json_bytes=2000000, verify_ssl=True, block_private_networks=True)

Выполняет HTTP запрос с автоматическими retry при сетевых ошибках.
Блокирует private/loopback IP по умолчанию.
Поддерживает whitelist хостов через allow_hosts.
Автоматически парсит JSON ответы.
Редактирует чувствительные заголовки в логах.

Возвращает dict:
{
  "ok": bool,
  "status_code": int,
  "headers": dict,
  "body_text": str,
  "json": dict/list/None,
  "meta": {"elapsed_ms": int, "attempts": int, "target": str, "request_id": str},
  "error": {"type": str, "message": str, "retryable": bool, "details": dict} или None
}

invoke_many(calls, common_auth_headers=None, **common_kw)
Батчевый вызов. calls - список dict с параметрами для invoke_function.
common_auth_headers применяются ко всем вызовам.
Возвращает список результатов.
