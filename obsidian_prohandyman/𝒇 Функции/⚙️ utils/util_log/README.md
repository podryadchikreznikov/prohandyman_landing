util_log

Структурированное JSON логирование.

logger.py

JsonLogger(correlation_id=None, redactions=None)
Создает логгер с correlation_id для трейсинга запросов.
По умолчанию редактирует authorization, cookie, x-api-key заголовки.

Методы:
- log(level, msg, **fields) - базовый метод
- info(msg, **fields) - INFO уровень
- warn(msg, **fields) - WARN уровень
- error(msg, **fields) - ERROR уровень

Все логи выводятся в stdout как JSON строки с полями:
{"level": str, "msg": str, "ts_ms": int, "correlation_id": str, ...custom_fields}

redact_headers(headers)
Редактирует чувствительные заголовки перед логированием.
Возвращает dict с замененными значениями на "<redacted>".
