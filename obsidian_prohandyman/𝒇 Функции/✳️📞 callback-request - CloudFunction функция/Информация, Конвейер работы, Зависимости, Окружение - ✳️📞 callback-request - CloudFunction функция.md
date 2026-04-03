Идентификатор - d4ekm8kgr6oq7cfisc68
Имя - callback-request
Описание - Принять заявку из формы обратной связи и отправить письмо владельцу сайта через SMTP.
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
	-> Проверка contract-hash заголовков `X-Request-Schema-Hash` и `X-Response-Schema-Hash` по `contracts.json`.
	-> При несовпадении: возврат `426 OUTDATED_CLIENT_SCHEMA`.
	-> Валидация: требуется хотя бы один из `phone_number` или `email`.
	-> Формирование текста письма: plain text + HTML с деталями заявки.
	-> Получение из ENV адреса получателя (`CALLBACK_NOTIFY_EMAIL`).
	-> Отправка письма через SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`).
	-> Обработка ошибок провайдера/сети. Возврат 500 при сбоях.
	-> Все ответы дополняются CORS и anti‑cache заголовками.

На выходе:
	-> `200 OK`: `{ "message": "Callback request sent via email." }`
	-> `426 Upgrade Required`: `{ "error": { "code": "OUTDATED_CLIENT_SCHEMA", "message": string } }`
	-> `400 Bad Request`: При отсутствии обязательных полей или некорректном формате телефона.
	-> `500 Internal Server Error`: Ошибка конфигурации или отправки email.

---
#### Зависимости и окружение
- Необходимые утилиты:
	- `utils/util_log/logger.py` — JsonLogger для структурированного логирования
	- `utils/util_http/cors.py` — cors_headers, handle_preflight для CORS
	- `utils/util_http/request.py` — parse_event для парсинга запроса
	- `utils/util_http/response.py` — ok, bad_request, server_error, json_response для HTTP‑ответов
	- `utils/util_errors/exceptions.py` — AppError, Internal
	- `utils/util_errors/to_response.py` — app_error_to_http для маппинга ошибок
	- `utils/util_sms/sms_sender.py` — validate_phone_number для нормализации телефона
	- `contracts.json` — канонические contract hashes для лендингового API
- Переменные окружения:
	- `CALLBACK_NOTIFY_EMAIL` — адрес получателя, обычно `owner@подрядчик.com`
	- `SMTP_HOST` — SMTP-сервер, для REG.RU обычно `mail.hosting.reg.ru`
	- `SMTP_PORT` — порт SMTP, обычно `465` для SSL или `587` для STARTTLS
	- `SMTP_USERNAME` — логин почтового ящика
	- `SMTP_PASSWORD` — пароль почтового ящика
	- `SMTP_FROM_EMAIL` — адрес отправителя
	- `SMTP_FROM_NAME` — имя отправителя
	- `CALLBACK_EMAIL_SUBJECT` — тема письма
	- `CORS_ALLOW_ORIGIN` — опционально, по умолчанию "*"

Примечания:
- Функция не отправляет письма пользователю; сообщение всегда уходит на указанный `CALLBACK_NOTIFY_EMAIL`.
- Клиент обязан присылать заголовки `X-Request-Schema-Hash` и `X-Response-Schema-Hash`; при несовпадении функция возвращает `426 OUTDATED_CLIENT_SCHEMA`.
