Идентификатор - d4e3g2b9paopb4ob0j89
Описание - 💰 Управляет внутренними выплатами и финансовыми событиями сотрудников.
Точка входа - index.handler
Таймаут - 120 сек

---

### Конвейер работы

На входе:
	-> `Authorization: Bearer <jwt_token>`: обязательно.
	-> `x-request-schema-hash: <sha256>`: обязательно.
	-> `x-response-schema-hash: <sha256>`: обязательно.
	-> `action` (string, обязательно): тип действия — `deferred_create`, `cash_create`, `accrual_create`, `salary_upsert`, `salary_delete`, `fine_create`, `reward_create`, `dispatcher_settlement_create`.
	-> `firm_id` (string, обязательно): UUID фирмы (в теле запроса, должен совпадать с path firm_id).

		Для action=deferred_create:
		-> `user_id` (string, обязательно): UUID сотрудника.
		-> `deferred_until` (string, обязательно): дата/время, до которой начисление перенесено (ISO).

	Для action=accrual_create:
	-> `user_id` (string, обязательно): UUID сотрудника.

	Для action=cash_create:
	-> `user_id` (string, обязательно): UUID сотрудника.
	-> `user_name` (string, обязательно): имя сотрудника.
	-> `amount_kopeks` (int, обязательно): сумма в копейках.
	-> `accrual_event_id` (string, необязательное): UUID события начисления, к которому относится выплата.
	-> `payment_scope` (string, обязательно): `rewards_fines` / `salary` / `all`.
	-> `salary_payment_items` (array, обязательно для `salary`/`all`): элементы выплаты ЗП.
		-> `salary_id` (string, обязательно): UUID записи `employee_salary`.
		-> `amount_kopeks` (int, обязательно): сумма по элементу.
	-> `rewards_fines_payment` (object, обязательно для `rewards_fines`/`all`): часть выплаты по вознаграждениям/штрафам.
		-> `amount_kopeks` (int, обязательно): сумма по части выплаты.

	Для action=salary_upsert:
	-> `salary_id` (string, необязательное): UUID записи зарплаты (если передан — обновление).
	-> `user_id` (string, обязательно): UUID сотрудника.
	-> `amount_kopeks` (int, обязательно): сумма в копейках.
	-> `payout_date` (string, обязательно): дата выплаты (YYYY-MM-DD).
	-> `effective_from` (string, обязательно): дата вступления записи зарплаты в силу (ISO).

	Для action=salary_delete:
	-> `salary_id` (string, обязательно): UUID записи зарплаты для удаления.
	-> `user_id` (string, обязательно): UUID сотрудника.

	Для action=fine_create:
	-> `user_id` (string, обязательно): UUID сотрудника.
	-> `object_id` (string, обязательно): UUID объекта.
	-> `theme` (string, обязательно): тема штрафа.
	-> `amount_kopeks` (int, обязательно): сумма в копейках.
	-> `message` (string, необязательное): сообщение.
	-> `attachments_json` (array|string|null, необязательное): вложения.
	-> `source_kind` (string, необязательное): тип связи (`appeal_compensation`).
	-> `source_appeal_id` (string, необязательное): UUID спора-источника.
	-> `source_event_type` (string, необязательное): тип исходного события (`fine`).
	-> `source_event_id` (string, необязательное): UUID исходного события (штрафа).

	Для action=reward_create:
	-> `user_id` (string, обязательно): UUID сотрудника.
	-> `object_id` (string, обязательно): UUID объекта.
	-> `theme` (string, обязательно): тема вознаграждения.
	-> `amount_kopeks` (int, обязательно): сумма в копейках.
	-> `message` (string, необязательное): сообщение.
	-> `attachments_json` (array|string|null, необязательное): вложения.

	Для action=dispatcher_settlement_create:
	-> `attribution_type` (string, обязательно): тип расчета — `dispatcher` или `nominal`.
	-> `dispatcher_id` (string|null, обязательно для `dispatcher`, отсутствует для `nominal`): UUID диспетчера.
	-> `dispatcher_name` (string, необязательное): имя диспетчера; при отсутствии сервер пытается достроить его по `dispatcher_id`.
	-> `period_ended_at` (string, обязательно): ISO timestamp, которым клиент фиксирует верхнюю границу текущего расчета.
	-> `source_last_settlement_event_id` (string|null, обязательно): event_id предыдущего расчета по тому же scope; если предыдущего расчета не было, должно быть `null`.
	-> `source_last_settlement_created_at` (string|null, обязательно): created_at предыдущего расчета по тому же scope; если предыдущего расчета не было, должно быть `null`.
	-> `amount_due_kopeks` (int, обязательно): итоговая сумма, которая должна быть выплачена по текущему расчету.
	-> `amount_paid_kopeks` (int, обязательно): сумма, реально выплаченная диспетчеру в рамках текущего расчета.
	-> `workers` (array, обязательно): массив работников, из которого можно точно восстановить расчет.
		-> `worker_user_id` (string, обязательно): UUID работника.
		-> `worker_name` (string, обязательно): имя работника.
		-> `dispatcher_id` (string|null, обязательно для `dispatcher`, отсутствует для `nominal`): должен совпадать со scope события.
		-> `attribution_type` (string, обязательно): должен совпадать с top-level `attribution_type`.
		-> `percent_snapshot` (number, обязательно): процент диспетчера, примененный к работнику в текущем расчете.
		-> `current_period_due_kopeks` (int, обязательно): сколько начислено за период после предыдущего расчета.
		-> `current_period_paid_kopeks` (int, обязательно): сколько из текущего периода выплачено сейчас.
		-> `previous_debt_kopeks` (int, обязательно): остаток долга по предыдущим расчетам на момент создания события.
		-> `amount_due_kopeks` (int, обязательно): `current_period_due_kopeks + previous_debt_kopeks`.
		-> `amount_paid_kopeks` (int, обязательно): фактически выплаченная сумма по работнику в этом расчете.
		-> `amount_remaining_kopeks` (int, обязательно): остаток после текущей выплаты.
		-> `shifts` (array, обязательно): массив смен текущего периода, формирующих `current_period_due_kopeks`.
			-> `shift_event_id` (string, обязательно): event_id события смены; уникален в рамках запроса.
			-> `gross_amount_kopeks` (int, обязательно): базовая сумма смены до удержания диспетчера.
			-> `withheld_amount_kopeks` (int, обязательно): сумма удержания/начисления диспетчеру по этой смене.
		-> `previous_debts` (array, обязательно): открытые долги по прошлым событиям `dispatcher_settlement`.
			-> `source_settlement_event_id` (string, обязательно): event_id предыдущего расчета.
			-> `remaining_kopeks` (int, обязательно): непогашенный остаток по этому событию.
		-> `debt_closures` (array, обязательно): какие старые долги закрываются этой выплатой.
			-> `source_settlement_event_id` (string, обязательно): event_id расчета, долг по которому закрывается.
			-> `amount_kopeks` (int, обязательно): сумма закрытия по указанному долгу.

Внутренняя работа:
	-> Логирование:
		-> Логирование event/context и request_id через YCLogger (hard_logger).
		-> Супер-логирование через `hlog.hard()` для ключевых точек.
	-> Парсинг запроса:
		-> Парсинг event в нормализованный запрос через parse_event.
	-> Проверка контракта схем:
		-> Извлечение `contract.request_schema_hash` и `contract.response_schema_hash` из тела запроса или заголовков `x-request-schema-hash`, `x-response-schema-hash`.
		-> При наличии заголовков хеши добавляются в `contract`, не затирая заданные значения.
		-> Сравнение с каноническими хешами из [[contracts.json - ✳️💰 payroll-manager - CloudFunction функция]] через `check_contract()`.
		-> Если хеши не совпадают: возврат `426 Upgrade Required` с кодом `OUTDATED_CLIENT_SCHEMA`.
	-> Авторизация:
		-> Чтение normalized identity context из `requestContext.authorizer`.
		-> Проверка полей `auth_type`, `principal_type`, `principal_id`, `user_id`, `firm_id`, `role_type`.
		-> Проверка `auth_type=employee_jwt` и `principal_type=employee`.
		-> Извлечение `caller_user_id` и `caller_role_type` из `requestContext.authorizer`.
	-> Валидация:
		-> Проверка `firm_id` на UUID через `is_uuid()`, совпадение с `path.firm_id` и совпадение с `requestContext.authorizer.firm_id`.
		-> Проверка обязательных полей в зависимости от action.
		-> Проверка UUID формата `user_id`, `salary_id`, `object_id`.
		-> Проверка `amount_kopeks` >= 0.
		-> Валидация `attachments_json` через metadata-validator (schema_name=attachments_json, entity_type=field_type) при наличии.
		-> Внутренний вызов в metadata-validator идет как internal HTTP invoke; по этой цепочке пишутся логи `payroll_manager.internal_invoke.*` и `payroll_manager.metadata_validator.*`.
	-> Подключение к YDB:
		-> Получение credentials через Lockbox (`YcSaLoader`).
		-> Подключение к firms-database.
		-> Подключение к notices-database (таблица employee_salary).

	-> Проверка прав:
		-> SELECT `role_type` caller'а из `firm_employees` по (firm_id, caller_user_id).
		-> Если role_type не в ['owner','admin','accountant','manager','foreman','foreman_foreman']: возврат 403.

	Для action=salary_upsert:
	-> Транзакция в notices-database:
	-> Проверка существования сотрудника в firms-database по (firm_id, user_id).
	-> Если не найден: возврат 404.
	-> Если salary_id передан: SELECT записи по (salary_id, firm_id) и UPDATE amount/payout_date/status/effective_from/deleted_at/updated_at.
	-> Если salary_id не передан: INSERT новой записи (salary_id=UUIDv4, created_at/updated_at=now, last_payout_at=NULL, status=`active`, effective_from=payload, deleted_at=NULL).
	-> После upsert отправка уведомления `your_salary_changed` с полным snapshot записей зарплаты.

	Для action=salary_delete:
	-> Транзакция в notices-database:
	-> SELECT записи `employee_salary` по (salary_id, firm_id, user_id).
	-> Если не найдена: возврат 404.
	-> UPDATE записи `employee_salary`: `status = "deleted"`, `deleted_at = now`, `updated_at = now`.
	-> После delete отправка уведомления `your_salary_changed` с полным snapshot записей зарплаты.

	Для action=deferred_create:
	-> Проверка сотрудника в firms-database по (firm_id, user_id).
	-> Формирование server-side `event_at = now_utc()`.
	-> Запись события `deferred` через sequence-number-generator:
		-> state_json включает firm_id, user_id, deferred_until, event_at.

	Для action=accrual_create:
	-> Проверка сотрудника в firms-database по (firm_id, user_id).
	-> Формирование server-side `event_at = now_utc()`.
	-> Чтение имени сотрудника из firms-database (`UserProfiles`).
	-> Чтение server-side snapshot записей `employee_salary` на момент `event_at` из notices-database.
	-> Чтение релевантных записей `finance_events` по фирме из events-log database.
	-> Чтение `state_json` по event_id из metadata-system (`aggregate_state_{firm_id}`).
	-> Отбор событий сотрудника по `user_id` из `state_json`.
	-> Поиск последнего события `accrual` для отсечения уже начисленных источников.
	-> Чтение `cash` после последнего `accrual` и вычитание уже выплаченных сумм из зарплатной части и из части `rewards_fines`.
	-> Нормализация `employee_salary_snapshot`: `amount_kopeks` в payload заменяется на остаток к выплате, дополнительно включаются `source_amount_kopeks`, `paid_kopeks`, `remaining_kopeks`, `overpaid_kopeks`.
	-> Расчет суммы начисления по событиям после последнего `accrual`:
		-> положительные источники: `reward`, `shift_end`, `deal_complete`;
		-> отрицательные источники: `fine`;
		-> для `shift_end` из суммы события вычитается `dispatcher_attribution.percent_snapshot`, если у сотрудника есть активная атрибуция диспетчера;
		-> `deal_complete` учитывается по полной сумме события, без отдельного вычитания процента диспетчера;
		-> зарплатная часть берется из нормализованного `employee_salary_snapshot` с остатками к выплате.
	-> Чтение последней `dispatcher_attribution` по (firm_id, user_id) из firms-database.
	-> Формирование `deferred_state` по последнему событию `deferred` после последнего `accrual`.
	-> Формирование payload события `accrual` по схеме `schema_version=3` из server-side queue snapshot:
		-> state_json включает `firm_id`, `user_id`, `user_name`, `amount_kopeks`, `event_at`.
		-> state_json включает `period_ended_at`, а также `period_started_at`, `source_last_accrual_event_id`, `source_last_accrual_created_at`, если они есть в queue snapshot.
		-> state_json включает `totals` только с ключами `salary_total_kopeks`, `rewards_total_kopeks`, `deals_total_kopeks`, `shifts_total_kopeks`, `fines_total_kopeks`, `withholds_total_kopeks`, `events_total_count`.
		-> state_json включает `dispatcher_attribution`, `deferred_state`, `employee_salary_snapshot`, `fines`, `rewards`, `shifts`, `deals`, `withholds`.
		-> В event payload не включаются legacy-поля `payment_scope`, `salary_payment_items`, `rewards_fines_payment`, `payment_components`, `salary_total_kopeks`, `rewards_fines_total_kopeks`.

	Для action=cash_create:
	-> Проверка сотрудника в firms-database по (firm_id, user_id).
	-> Формирование server-side `event_at = now_utc()`.
	-> Чтение действующего на момент `event_at` среза записей `employee_salary` по (firm_id, user_id) из notices-database с фильтром `effective_from <= event_at` и `(deleted_at IS NULL OR deleted_at > event_at)`.
	-> Валидация структуры выплаты:
		-> Проверка `payment_scope`.
		-> Проверка `salary_payment_items` и/или `rewards_fines_payment` в зависимости от `payment_scope`.
		-> Проверка `salary_id` в `salary_payment_items` как ссылки на `employee_salary`.
		-> Проверка равенства `amount_kopeks` сумме breakdown.
		-> Поля `paid_at` в breakdown формируются сервером и равны `event_at`.
	-> Запись события `cash` через sequence-number-generator:
		-> state_json включает firm_id, user_id, user_name, amount_kopeks, event_at.
		-> state_json может включать `accrual_event_id`.
		-> state_json включает `employee_salary_snapshot` (полный срез `employee_salary` по сотруднику).
		-> state_json включает `payment_scope`, `salary_payment_items`, `rewards_fines_payment`, `payment_components`, `salary_total_kopeks`, `rewards_fines_total_kopeks`.
	-> Обновление `employee_salary.last_payout_at` в notices-database:
		-> Для каждого `salary_id` из `salary_payment_items` записывается максимальный `paid_at` из сформированного сервером breakdown.

	Для action=fine_create:
	-> Проверка сотрудника в firms-database по (firm_id, user_id).
	-> Формирование server-side `event_at = now_utc()`.
	-> Запись события `fine` через sequence-number-generator:
		-> state_json включает firm_id, user_id, object_id, theme, amount_kopeks, message, attachments_json, event_at.

	Для action=reward_create:
	-> Проверка сотрудника в firms-database по (firm_id, user_id).
	-> Формирование server-side `event_at = now_utc()`.
	-> Запись события `reward` через sequence-number-generator:
		-> state_json включает firm_id, user_id, object_id, theme, amount_kopeks, message, attachments_json, event_at.
		-> state_json может включать `source_kind`, `source_appeal_id`, `source_event_type`, `source_event_id`.
		-> Для `reward` используется schema_version=3 (v2 сохранен для обратной совместимости чтения старых событий).

	Для action=dispatcher_settlement_create:
	-> Чтение только событий `dispatcher_settlement` по фирме из `finance_events` и их `state_json` из metadata-system.
	-> Фильтрация по scope расчета:
		-> `attribution_type=dispatcher`: учитываются только события того же `dispatcher_id`.
		-> `attribution_type=nominal`: учитываются только nominal-расчеты без `dispatcher_id`.
	-> Оптимистическая блокировка по истории:
		-> `source_last_settlement_event_id` и `source_last_settlement_created_at` должны точно совпадать с последним уже существующим расчетом по тому же scope.
		-> Если между чтением очереди и созданием события появился новый расчет, запрос отклоняется.
	-> Восстановление открытых долгов по работникам:
		-> Сервер строит текущий хвост задолженности из прошлых `dispatcher_settlement`, вычитая все уже записанные `debt_closures`.
		-> `workers[].previous_debts` должен в точности совпасть с фактическим серверным хвостом долга.
	-> Валидация арифметики по каждому работнику:
		-> `current_period_due_kopeks = sum(shifts[].withheld_amount_kopeks)`.
		-> `previous_debt_kopeks = sum(previous_debts[].remaining_kopeks)`.
		-> `amount_due_kopeks = current_period_due_kopeks + previous_debt_kopeks`.
		-> `amount_paid_kopeks = current_period_paid_kopeks + sum(debt_closures[].amount_kopeks)`.
		-> `amount_remaining_kopeks = amount_due_kopeks - amount_paid_kopeks`.
		-> `amount_paid_kopeks` не может превышать `amount_due_kopeks`.
	-> Валидация ссылочной целостности:
		-> `workers[].shifts[].shift_event_id` должен быть уникален в рамках запроса.
		-> `debt_closures[].source_settlement_event_id` должен ссылаться только на реально открытый предыдущий долг этого же работника.
		-> Сумма закрытия по одному прошлому расчету не может превышать его текущий остаток.
	-> Формирование append-only события `dispatcher_settlement` через sequence-number-generator:
		-> state_json включает `firm_id`, `dispatcher_id`, `dispatcher_name`, `attribution_type`, `event_at`, `period_started_at`, `period_ended_at`.
		-> state_json включает top-level суммы `amount_due_kopeks`, `amount_paid_kopeks`, `amount_remaining_kopeks`.
		-> state_json включает `source_last_settlement_event_id`, `source_last_settlement_created_at`, `totals`, `workers`.
		-> Событие создается только как новая запись; механики редактирования/перезаписи/удаления для этого типа события не предусмотрены.

	-> Обработка исключений:
		-> Возврат 400/401/403/404/426/500.
	-> Кэширование runtime-инстанса: credentials из Lockbox и YDB SessionPool сохраняются в глобальных переменных и переиспользуются при warm-start.

На выходе:
	-> `200 OK` (salary_upsert): `{ "message": "Salary saved", "firm_id": string, "salary_id": string, "user_id": string }`.
	-> `200 OK` (salary_delete): `{ "message": "Salary deleted", "firm_id": string, "salary_id": string, "user_id": string }`.
	-> `201 Created` (deferred_create): `{ "message": "Deferred payout created", "event_id": string, "firm_id": string, "user_id": string }`.
	-> `201 Created` (accrual_create): `{ "message": "Accrual created", "event_id": string, "firm_id": string, "user_id": string }`.
	-> `201 Created` (cash_create): `{ "message": "Cash payout created", "event_id": string, "firm_id": string, "user_id": string }`.
	-> `201 Created` (fine_create): `{ "message": "Fine created", "event_id": string, "firm_id": string, "user_id": string }`.
	-> `201 Created` (reward_create): `{ "message": "Reward created", "event_id": string, "firm_id": string, "user_id": string }`.
	-> `201 Created` (dispatcher_settlement_create): `{ "message": "Dispatcher settlement created", "event_id": string, "firm_id": string, "dispatcher_id": string|null, "attribution_type": string }`.
	-> `426 Upgrade Required`: Если схемы клиента устарели: `{ "code": "OUTDATED_CLIENT_SCHEMA", "message": string }`.
	-> `400 Bad Request`: Если входные параметры некорректны.
	-> `401 Unauthorized`: Если авторизация не пройдена.
	-> `403 Forbidden`: Если недостаточно прав.
	-> `404 Not Found`: Если сотрудник/запись зарплаты не найдены.
	-> `500 Internal Server Error`: Если произошла внутренняя ошибка.

---

Зависимости и окружение
- Необходимые утилиты: `utils/util_http/request.py` (parse_event), `utils/util_http/response.py` (ok/created/bad_request/unauthorized/forbidden/not_found/server_error), `utils/util_log/logger.py` (JsonLogger), `utils/util_log/yc_logger.py` (YCLogger), `utils/util_time/index.py` (now_utc/parse_iso_utc), `utils/util_ydb/driver.py` (get_session_pool), `utils/util_contract/validator.py` (check_contract), `utils/util_contract/schema_hashes.py` (get_expected_schema_hashes), `utils/util_invoke/invoke.py` (invoke_function), `utils/util_yc_sa/loader.py` (YcSaLoader), `utils/util_metadata/*` (parse_json_value)
- Переменные окружения:
	- `YDB_ENDPOINT_FIRMS`, `YDB_DATABASE_FIRMS` [[💾 firms-database - База данных YandexDatabase]]
	- `YDB_ENDPOINT_NOTICES`, `YDB_DATABASE_NOTICES` [[💾 notices-database - База данных YandexDatabase]]
	- `SA_AUTHKEY_LOCKBOX_SECRET_NAME` [[🗝️  sa-functions-runtime - ключ доступа в lockbox]]
	- `FUNCTION_ID_SEQUENCE_NUMBER_GENERATOR` (UID CloudFunction sequence-number-generator) [[Информация, Конвейер работы, Зависимости, Окружение - ✳️🔢 sequence-number-generator - CloudFunction функция]]
	- `SEQUENCE_GENERATOR_REQUEST_SCHEMA_HASH` (response_schema_hash для sequence-number-generator)
	- `SEQUENCE_GENERATOR_RESPONSE_SCHEMA_HASH` (response_schema_hash для sequence-number-generator)
	- `FN_METADATA_VALIDATOR` (UID CloudFunction metadata-validator) [[Информация, Конвейер работы, Зависимости, Окружение - ✳️🧩 metadata-validator - CloudFunction функция]]
	- `METADATA_VALIDATOR_REQUEST_SCHEMA_HASH` (request_schema_hash для metadata-validator)
	- `METADATA_VALIDATOR_RESPONSE_SCHEMA_HASH` (response_schema_hash для metadata-validator)
	- `YDB_ENDPOINT_EVENTS_LOG`, `YDB_DATABASE_EVENTS_LOG` (events-log database: чтение `finance_events`)
	- `YDB_ENDPOINT_META`, `YDB_DATABASE_META` (metadata-system: чтение `aggregate_state_{firm_id}`)
	- `YMQ_QUEUE_URL` (URL очереди уведомлений) [[📨 push-notifications-jobs - Message Queue Очередь]]
	- `YMQ_FOLDER_ID` (folder_id для `X-Amz-Security-Token`) [[📨 push-notifications-jobs - Message Queue Очередь]]
	- `YMQ_LOCKBOX_SECRET_ID` (Lockbox secret id с `access_key_id` и `secret_access_key` для YMQ)
	- `LOG_STREAM_NAME` (опционально, default="payroll-manager")
	- `HARD_LOG_SYMBOL` (опционально, default="🧨")

