util_errors

Стандартизированные исключения и конвертация в HTTP ответы.

exceptions.py

AppError(code, message, http_status=400, details=None, retryable=False)
Базовое исключение приложения. Содержит code, message, http_status, details, retryable.

Готовые классы:
- BadRequest(message) - 400
- Unauthorized(message) - 401
- Forbidden(message) - 403
- NotFound(message) - 404
- Conflict(message) - 409
- RateLimited(message) - 429, retryable=True
- Internal(message) - 500

Использование: raise NotFound("User not found")

to_response.py

app_error_to_http(err)
Конвертирует AppError в HTTP response dict.
Возвращает {"statusCode": int, "headers": {...}, "body": json}
Формат body: {"error": {"code": str, "message": str, "details": dict}}
