util_http

Парсинг HTTP запросов, формирование ответов, CORS.

request.py

parse_event(event, action_fields=("action",), max_body_bytes=1000000, assume_json=True)
Парсит API Gateway event. Извлекает body (JSON/text), query, headers, path_params, action, bearer token.
Декодирует base64 если isBase64Encoded=true.
Возвращает ParsedRequest dict с полями: body_dict, body_text, query, headers, path_params, action, bearer.
Выбрасывает EventParseError при ошибках.

response.py

json_response(code, payload, headers=None)
Создает HTTP response с JSON телом.

Готовые функции:
- ok(data) - 200
- created(data) - 201
- bad_request(msg) - 400
- unauthorized(msg) - 401
- forbidden(msg) - 403
- not_found(msg) - 404
- conflict(msg) - 409
- too_many(msg) - 429
- server_error(msg) - 500

Все возвращают {"statusCode": int, "headers": {...}, "body": json_string}

cors.py

cors_headers(allow_origin="*", allow_headers="...", allow_methods="GET,POST,OPTIONS", allow_credentials=False)
Возвращает dict с CORS заголовками.

handle_preflight(event_headers, allow_origin="*", allow_credentials=False)
Проверяет OPTIONS preflight запрос. Возвращает 204 response или None.
