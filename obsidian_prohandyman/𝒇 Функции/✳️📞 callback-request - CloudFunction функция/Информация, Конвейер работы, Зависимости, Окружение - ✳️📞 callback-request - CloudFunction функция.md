Идентификатор - d4ekm8kgr6oq7cfisc68
Имя - callback-request
Описание - Принять контактные данные лида и отправить SMS руководителю/оператору о заявке на обратный звонок.
Точка входа - index.handler
Таймаут - 15 сек

---

На входе:
	-> `phone_number` (string, обязательный если нет email): Номер телефона лида (E.164, можно 8/7, `+` не обязателен).
	-> `email` (string, обязательный если нет phone_number): Email лида.
	-> `user_name` (string, опционально): Имя/как обращаться.
	-> `comment` (string, опционально): Короткий комментарий от пользователя.

Внутренняя работа:
	-> CORS preflight: обработка OPTIONS с возвратом CORS‑заголовков.
	-> Парсинг входных данных (`parse_event`), нормализация телефона (`validate_phone_number`).
	-> Валидация: требуется хотя бы один из `phone_number` или `email`.
	-> Формирование текста: «Оставлена заявка на обратный звонок» + детали (имя, комментарий, email/телефон лида).
	-> Получение из ENV номера получателя (`CALLBACK_NOTIFY_PHONE`), нормализация.
	-> Отправка SMS через SMSC.ru (`SMSC_LOGIN`/`SMSC_PASSWORD`).
	-> Обработка ошибок провайдера/сети. Возврат 500 при сбоях.
	-> Все ответы дополняются CORS и anti‑cache заголовками.

На выходе:
	-> `200 OK`: `{ "message": "Callback request sent via WhatsApp." }`
	-> `400 Bad Request`: При отсутствии обязательных полей или некорректном формате телефона.
	-> `500 Internal Server Error`: Ошибка конфигурации или отправки SMS.

---
#### Зависимости и окружение
- Необходимые утилиты:
	- `utils/util_log/logger.py` — JsonLogger для структурированного логирования
	- `utils/util_http/cors.py` — cors_headers, handle_preflight для CORS
	- `utils/util_http/request.py` — parse_event для парсинга запроса
	- `utils/util_http/response.py` — ok, bad_request, server_error для HTTP‑ответов
	- `utils/util_errors/exceptions.py` — AppError, Internal
	- `utils/util_errors/to_response.py` — app_error_to_http для маппинга ошибок
	- `utils/util_json/index.py` — loads_safe при необходимости
	- `utils/util_sms/sms_sender.py` — validate_phone_number для нормализации телефона
- Переменные окружения:
	- `SMSC_LOGIN` — логин для SMSC.ru
	- `SMSC_PASSWORD` — пароль для SMSC.ru
	- `CALLBACK_NOTIFY_PHONE` — номер получателя (руководитель/оператор/секретарь)
	- `CORS_ALLOW_ORIGIN` — опционально, по умолчанию "*"

Примечания:
- Функция не отправляет SMS пользователю; сообщение всегда уходит на указанный `CALLBACK_NOTIFY_PHONE`.
