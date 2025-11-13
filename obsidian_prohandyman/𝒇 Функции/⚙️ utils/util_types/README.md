util_types

TypedDict определения для типизации.

result.py

ErrorInfo
TypedDict с полями: type, message, retryable, details.
Используется для структурированного описания ошибок.

Result
TypedDict с полями: ok, error, data, meta.
Стандартный формат результата операции.
ok - bool успешности
error - ErrorInfo или None
data - любые данные результата
meta - метаинформация (timing, request_id и т.д.)
