util_time

Работа с UTC временем и timestamp конвертация.

index.py

now_utc()
Возвращает текущее UTC время как datetime объект.

parse_iso_utc(s)
Парсит ISO 8601 строку в datetime UTC. Поддерживает Z суффикс.

to_ts_us(dt)
Конвертирует datetime в микросекунды (int).

from_ts_us(us)
Конвертирует микросекунды в datetime UTC.

to_ts_ms(dt)
Конвертирует datetime в миллисекунды (int).

from_ts_ms(ms)
Конвертирует миллисекунды в datetime UTC.
