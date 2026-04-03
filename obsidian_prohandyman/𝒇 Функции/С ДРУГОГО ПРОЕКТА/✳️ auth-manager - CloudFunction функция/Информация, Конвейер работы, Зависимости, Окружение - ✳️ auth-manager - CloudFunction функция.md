
Идентификатор - d4ee34ulmmi0bgphsvhq
Описание - 🔐 Единый менеджер авторизации: логин, регистрация, СМС, сброс пароля, сброс сеансов.

Точка входа - index.handler
Таймаут - 120 сек

---
На входе:
	-> `action` (string, обязательно): одно из:
		- `login`
		- `register`
		- `resend_code`
		- `verify_code`
		- `reset_password`
		- `reset_sessions`
		- `get_user_data`
	-> `phone_number` (string, обязательно для всех action кроме `get_user_data`): номер телефона.
	-> `password` (string, обязательно для `login`, `register`, `reset_sessions`): пароль.
	-> `new_password` (string, обязательно для `reset_password`): новый пароль.
	-> `code` (string, обязательно для `verify_code`): код подтверждения.
	-> `user_type` (string, обязательно): `user` или `dispatcher`.

Внутренняя работа:
	-> Логирование:
		-> Логирование event/context и request_id.
	-> Парсинг запроса:
		-> Парсинг event в нормализованный запрос.
		-> Определение `action`.
	-> Проверка контракта схем:
		-> Извлечение `contract.request_schema_hash` и `contract.response_schema_hash` из тела запроса.
		-> Сравнение с каноническими хешами из [[contracts.json - ✳️ auth-manager - CloudFunction функция]].
		-> Если хеши не совпадают: возврат `426 Upgrade Required` с кодом `OUTDATED_CLIENT_SCHEMA`.
	-> Валидация:
		-> Проверка обязательных параметров по `action`.
		-> Нормализация `phone_number`.
	-> Подключение к YDB:
		-> Создание пула сессий для firms-database.
	-> Маршрутизация по action:
		-> Если `action=login`: проверка пароля, генерация кода, отправка СМС или выдача токена в режиме теста.
		-> Если `action=register`: создание/обновление записи пользователя, генерация кода, отправка СМС или выдача токена в режиме теста.
		-> Если `action=resend_code`: повторная генерация кода и отправка СМС.
		-> Если `action=verify_code`: проверка кода, выдача токена.
		-> Если `action=reset_password`: обновление пароля, генерация кода, отправка СМС.
		-> Если `action=reset_sessions`: проверка пароля, сброс jwt_token.
		-> Если `action=get_user_data`: получение данных пользователя по user_id (из body/query или JWT).
	-> Инициализация metadata-system:
		-> При `action=register` и `action=verify_code` (успешный сценарий): идемпотентно создаётся таблица `aggregate_state_{user_id}` в базе metadata-system.
	-> Обработка исключений:
		-> Возврат 400/401/404/409/423/429/500.

На выходе:
	-> `200 OK`: Если `action=verify_code` или включен AUTO_CONFIRM_MODE: `{ "token": "<jwt_token>" }`.
	-> `200 OK`: Если `action=get_user_data`: `{ "user_id": string, "email": string|null, "phone_number": string, "status": string, "last_login_at": string|null, "created_at": string, "updated_at": string }`.
	-> `200 OK`: Если выполнено действие с отправкой кода: `{ "message": "Verification code sent.", "phone_number": string }`.
	-> `426 Upgrade Required`: Если схемы клиента устарели: `{ "code": "OUTDATED_CLIENT_SCHEMA", "message": string }`.
	-> `400 Bad Request`: Если входные параметры некорректны.
	-> `401 Unauthorized`: Если пароль неверный или отсутствует авторизация.
	-> `404 Not Found`: Если пользователь не найден.
	-> `409 Conflict`: Если пользователь уже существует.
	-> `423 Locked`: Если пользователь заблокирован.
	-> `429 Too Many Requests`: Если превышен лимит.
	-> `500 Internal Server Error`: Если произошла внутренняя ошибка.


---

Зависимости и окружение
- Необходимые утилиты: `utils/util_http/*` (парсинг HTTP), `utils/util_ydb/driver.py` (YDB), `utils/util_ydb/credentials.py` (credentials), `utils/util_sms/sms_sender.py` (SMS)
- Переменные окружения:
	- `YDB_ENDPOINT_FIRMS`, `YDB_DATABASE_FIRMS` [[💾 firms-database - База данных YandexDatabase]]
	- `JWT_SECRET` [[🛡️ auth-gate - CloudFunction функция]]
	- `SMSC_LOGIN` [[Информация, Конвейер работы, Зависимости, Окружение - ✳️ auth-manager - CloudFunction функция]]
	- `SMSC_PASSWORD` [[Информация, Конвейер работы, Зависимости, Окружение - ✳️ auth-manager - CloudFunction функция]]
	- `AUTO_CONFIRM_MODE` (опционально, default="false") [[Информация, Конвейер работы, Зависимости, Окружение - ✳️ auth-manager - CloudFunction функция]]
	- `AUTH_MANAGER_USERS_TABLE` (опционально, default="Users") [[💾 firms-database - База данных YandexDatabase]]
	- `AUTH_MANAGER_DISPATCHERS_TABLE` (опционально, default="Dispatchers") [[💾 firms-database - База данных YandexDatabase]]
	- `YDB_ENDPOINT_META`, `YDB_DATABASE_META` [[💾 metadata-system - База данных YandexDatabase]]
	- `SA_AUTHKEY_LOCKBOX_SECRET_NAME` [[🗝️  sa-functions-runtime - ключ доступа в lockbox]]
	- `LOG_STREAM_NAME` (опционально, default="auth-manager") [[Информация, Зависимости, Окружение - ✳️📣 demo-broadcast-consumer - CloudFunction функция]]
	- `HARD_LOG_SYMBOL` (опционально, default="🧨") [[Информация, Зависимости, Окружение - ✳️📣 demo-broadcast-consumer - CloudFunction функция]]
