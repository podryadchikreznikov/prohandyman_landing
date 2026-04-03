
Идентификатор - d4ei87m47qchac3ak8br
Описание - 📊 Предоставляет аналитические данные по объектам и финансам фирмы через сводные геттеры
Точка входа - index.handler
Таймаут - 180 сек

---

### Конвейер работы

На входе:
-> `Authorization: Bearer <JWT>`: JWT токен пользователя, обязателен
-> `x-request-schema-hash: <hash>`: хэш схемы запроса из contracts.json, обязателен
-> `x-response-schema-hash: <hash>`: хэш схемы ответа из contracts.json, обязателен
-> `firm_id`: идентификатор фирмы в path `/firms/{firm_id}/...`, обязателен
-> `action`: тип операции в теле запроса, обязателен
-> `contract.request_schema_hash`: хэш схемы запроса в теле, обязателен
-> `contract.response_schema_hash`: хэш схемы ответа в теле, обязателен

Для `action: object_finance_history`:
-> `object_id`: идентификатор объекта в теле запроса, обязателен
-> `month`: месяц для анализа (1-12) в теле запроса, обязателен
-> `year`: год для анализа в теле запроса, обязателен

Для `action: object_activity_presence`:
-> `object_id`: идентификатор объекта в теле запроса, обязателен
-> `date`: дата в формате YYYY-MM-DD в теле запроса, обязателен

Для `action: my_object_presence`:
-> дополнительные поля не требуются

Для `action: object_activity_timeline`:
-> `object_id`: идентификатор объекта в теле запроса, обязателен
-> `date`: дата в формате YYYY-MM-DD в теле запроса, обязателен

Для `action: finance_turnover`:
-> дополнительные поля не требуются

Для `action: finance_gross_profit`:
-> дополнительные поля не требуются

Для `action: finance_objects_summary`:
 -> `search_query`: поисковый запрос (для векторного поиска по объектам), необязателен
 -> `page`: страница выдачи (0-based, по умолчанию 0), необязателен
 -> `page_size`: размер страницы (1..100, по умолчанию 20), необязателен

Для `action: employee_absences_total`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен

Для `action: employee_absences_disputed`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> Возвращает число прогулов сотрудника, по которым создан спор (`source_type=absence`)

Для `action: employee_absences_month`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен

Для `action: employee_absences_month_details`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен
-> `page`: страница выдачи (0-based), необязателен, по умолчанию `0`
-> `page_size`: размер страницы (1..100), необязателен; если не передан, возвращается полный список за месяц
-> Возвращает paged-массив прогулов с enrichment объектом и спором по каждому событию

Для `action: employee_attendance_month_summary`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен
-> `object_id`: идентификатор объекта для фильтрации по одному объекту в теле запроса, необязателен
-> Возвращает календарную сводку за месяц с плановыми/фактическими часами, списком объектов и totals

Для `action: employee_attendance_day_details`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `date`: дата в формате YYYY-MM-DD в теле запроса, обязателен
-> `object_id`: идентификатор объекта для фильтрации по одному объекту в теле запроса, необязателен
-> Возвращает все релевантные события дня, фактические/плановые часы и число уникальных объектов за выбранный день

Для `action: employee_calendar_day_upcoming`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `date`: дата в формате YYYY-MM-DD в теле запроса, обязателен
-> `object_id`: идентификатор объекта для фильтрации по одному объекту в теле запроса, необязателен
-> Возвращает ожидающие и активные смены/сделки выбранного сотрудника, которые реально относятся к выбранному дню: для сущностей с `start_at` используется пересечение с UTC-окном суток, для сущностей без `start_at` используются только записи, созданные в этот день, а archived-объекты из upcoming исключаются

Для `action: employee_calendar_day_period`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `date`: дата в формате YYYY-MM-DD в теле запроса, обязателен
-> `object_id`: идентификатор объекта для фильтрации по одному объекту в теле запроса, необязателен
-> Возвращает завершенные, завершенные принудительно, отмененные и отклоненные смены/сделки выбранного сотрудника за день с enrichment worker/assigned_by/withholding/dispatcher attribution

Для `action: employee_finance_month_list`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен
-> `page`: страница выдачи (0-based), необязателен, по умолчанию `0`
-> `page_size`: размер страницы (1..100), необязателен, по умолчанию `20`
-> Возвращает paged-журнал финансовых событий за месяц; поле `total_pending_kopeks` и объект `month_preview` содержат канонический остаток к выплате на конец выбранного периода, а не арифметику журнала

Для `action: employee_finance_month_total`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен
-> Возвращает агрегаты месяца; поле `total_pending_kopeks` содержит канонический остаток к выплате на конец выбранного периода

Для `action: employee_finance_cash_plan`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, обязателен
-> `as_of`: ISO datetime для расчета плана на момент времени, необязателен (по умолчанию `now UTC`)
-> Возвращает breakdown для наличной выплаты: pending по вознаграждениям/штрафам, remaining по активным salary_id, сумму `total_to_cover_all_kopeks` и блок `dispatcher_settlement` по текущему расчету с диспетчером для этого работника

Для `action: payroll_queue`:
-> `user_id`: идентификатор сотрудника (UUID) в теле запроса, необязателен
-> `page`: страница выдачи (0-based), необязателен, по умолчанию `0`
-> `page_size`: размер страницы (1..100), необязателен, по умолчанию `20`
-> `as_of`: ISO datetime для расчета очереди выплат, обязателен
-> Возвращает paged-массив по worker/foreman фирмы с fines/rewards/shifts/deals/cash, salary snapshot, dispatcher attribution и deferred state

Для `action: payroll_history`:
-> `date`: дата YYYY-MM-DD для режима day, необязателен
-> `year`: год (2020-2100) для режима month, обязателен если `date` не передан
-> `month`: месяц (1-12) для режима month, обязателен если `date` не передан
-> `page`: страница выдачи (0-based), необязателен, по умолчанию `0`
-> `page_size`: размер страницы (1..100), необязателен, по умолчанию `20`
-> Возвращает paged-историю событий `accrual`; в month-режиме оставляет только `paid` и `deferred`

Для `action: dispatcher_settlement_queue`:
-> `attribution_type`: тип расчета, обязателен: `dispatcher` или `nominal`
-> `dispatcher_id`: UUID диспетчера, обязателен для `attribution_type=dispatcher`, отсутствует для `nominal`
-> `as_of`: ISO datetime верхней границы расчета, необязателен (по умолчанию `now UTC`)
-> `page`: страница выдачи (0-based), необязателен, по умолчанию `0`
-> `page_size`: размер страницы (1..100), необязателен, по умолчанию `20`
-> Возвращает очередь расчета с диспетчером по текущему scope: работников, смены текущего периода, открытые долги по прошлым `dispatcher_settlement` и агрегаты суммы к выплате

Для `action: dispatcher_withhold_accrual_year_total`:
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен

Для `action: dispatcher_withhold_accrual_year_percent_avg`:
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен

Для `action: dispatcher_withhold_accrual_month_total`:
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен

Для `action: dispatcher_withhold_accrual_month_percent_avg`:
-> `month`: месяц для расчета (1-12) в теле запроса, обязателен
-> `year`: год для расчета (2020-2100) в теле запроса, обязателен

Для `action: dispatcher_withhold_accrual_user_total`:
-> `user_id`: идентификатор работника (UUID) в теле запроса, обязателен
-> `year`: год для фильтрации (2020-2100) в теле запроса, необязателен
-> `month`: месяц для фильтрации (1-12) в теле запроса, необязателен (если указан, year обязателен)

Для `action: dispatcher_withhold_accrual_user_total_all_firms`:
-> `user_id`: идентификатор работника (UUID) в теле запроса, обязателен
-> `year`: год для фильтрации (2020-2100) в теле запроса, необязателен
-> `month`: месяц для фильтрации (1-12) в теле запроса, необязателен (если указан, year обязателен)
-> Расчет выполняется по всем фирмам, где worker является сотрудником (status: active_unattached/active_attached) и связан с диспетчером через `dispatcher_attributions`

Для `action: worker_month_work`:
-> `month`: месяц (1-12) в теле запроса, обязателен
-> `year`: год (2020-2100) в теле запроса, обязателен

Для `action: worker_fines_year_total`:
-> `year`: год (2020-2100) в теле запроса, обязателен

Для `action: worker_fines_month_list`:
-> `month`: месяц (1-12) в теле запроса, обязателен
-> `year`: год (2020-2100) в теле запроса, обязателен

Для `action: worker_fines_year_list_excluding_month`:
-> `month`: месяц (1-12), который исключается из года, в теле запроса, обязателен
-> `year`: год (2020-2100) в теле запроса, обязателен

Для `action: worker_fines_totals_all_firms`:
-> `year`: год (2020-2100) в теле запроса, необязателен (по умолчанию текущий)
-> `month`: месяц (1-12) в теле запроса, необязателен (по умолчанию текущий)
-> Возвращает суммы штрафов worker по всем фирмам: `all_time/year/month` + разбивка по фирмам

Для `action: worker_fines_list_all_firms`:
-> `page`: страница (0-based), необязателен, по умолчанию `0`
-> `page_size`: размер страницы (1..100), необязателен, по умолчанию `20`
-> `year`: год (2020-2100), необязателен
-> `month`: месяц (1-12), необязателен (если указан, `year` обязателен)
-> Возвращает paged-список штрафов worker по всем фирмам с enrichment фирмой/объектом/спором

Внутренняя работа:
-> Логирование: request_id, function_name, memory_limit_in_mb, deadline_ms, raw_event
-> Парсинг запроса:
  -> Извлечение headers, query, path_params, body с помощью `utils.parse_event`
  -> Если парсинг не удался, возврат `400 Bad Request`
-> Авторизация:
  -> Проверка наличия Bearer токена в заголовке Authorization
  -> Если токен отсутствует, возврат `401 Unauthorized`
  -> Верификация JWT токена с помощью `utils.verify_jwt` и `JWT_SECRET`
  -> Если токен невалиден, возврат `401 Unauthorized`
  -> Извлечение `caller_user_id` из payload токена
-> Валидация контракта:
  -> Извлечение хэшей из headers `x-request-schema-hash`, `x-response-schema-hash`
  -> Объединение с `contract` из body
  -> Получение expected_req_hash и expected_res_hash из contracts.json с помощью `utils.get_expected_schema_hashes`
  -> Проверка совпадения хэшей с помощью `utils.check_contract`
  -> Если хэши не совпадают, возврат `426 Upgrade Required`
-> Валидация входных данных:
  -> Проверка наличия и формата `firm_id`
  -> Если `firm_id` отсутствует или не UUID, возврат `400 Bad Request`
  -> Проверка совпадения `firm_id` из path и body
  -> Если не совпадают, возврат `400 Bad Request`
-> Получение credentials для YDB:
  -> Извлечение SA ключа из Lockbox через `SA_AUTHKEY_LOCKBOX_SECRET_NAME` с помощью `sa.get_ydb_credentials`
  -> Если не удалось получить, возврат `500 Internal Server Error`
-> Подключение к YDB:
  -> Создание session pool для firm-objects-database через `YDB_ENDPOINT_FIRM_OBJECTS` и `YDB_DATABASE_FIRM_OBJECTS`
  -> Создание session pool для firms-database через `YDB_ENDPOINT_FIRMS` и `YDB_DATABASE_FIRMS`
  -> Создание session pool для events-log-database через `YDB_ENDPOINT_EVENTS_LOG` и `YDB_DATABASE_EVENTS_LOG`
  -> Для action `object_finance_history`, `object_activity_presence`, `object_activity_timeline`, `finance_turnover`, `finance_gross_profit`, `finance_objects_summary`, `payroll_queue`, `payroll_history`, `dispatcher_settlement_queue`, `employee_attendance_month_summary`, `employee_attendance_day_details`, `employee_calendar_day_upcoming`, `employee_calendar_day_period` и action группы dispatcher/worker: создание session pool для metadata-system (чтение `state_json` из таблиц вида `aggregate_state_{firm_id}`) через `YDB_ENDPOINT_META` и `YDB_DATABASE_META`
  -> Для action `employee_finance_month_list`, `employee_finance_month_total`, `employee_finance_cash_plan` и `payroll_queue`: создание session pool для notices-database (`employee_salary`) через `YDB_ENDPOINT_NOTICES` и `YDB_DATABASE_NOTICES`
  -> Если подключения не удались, возврат `500 Internal Server Error`
-> Маршрутизация по action:
  -> Если `action == object_finance_history`, вызов `handle_object_finance_history`
  -> Если `action == object_activity_presence`, вызов `handle_object_activity_presence`
  -> Если `action == my_object_presence`, вызов `handle_my_object_presence`
  -> Если `action == object_activity_timeline`, вызов `handle_object_activity_timeline`
  -> Если `action == finance_turnover`, вызов `handle_finance_turnover`
  -> Если `action == finance_gross_profit`, вызов `handle_finance_gross_profit`
  -> Если `action == finance_objects_summary`, вызов `handle_finance_objects_summary`
  -> Если `action == employee_attendance_month_summary`, вызов `handle_employee_attendance_month_summary`
  -> Если `action == employee_attendance_day_details`, вызов `handle_employee_attendance_day_details`
  -> Если `action == employee_calendar_day_upcoming`, вызов `handle_employee_calendar_day_upcoming`
  -> Если `action == employee_calendar_day_period`, вызов `handle_employee_calendar_day_period`
  -> Если `action == employee_finance_month_list`, вызов `handle_employee_finance_month_list`
  -> Если `action == employee_finance_month_total`, вызов `handle_employee_finance_month_total`
  -> Если `action == payroll_queue`, вызов `handle_payroll_queue`
  -> Если `action == payroll_history`, вызов `handle_payroll_history`
  -> Если `action == dispatcher_settlement_queue`, вызов `handle_dispatcher_settlement_queue`
  -> Если action не поддерживается, возврат `400 Bad Request`
-> Обработка `object_finance_history`:
  -> Валидация наличия `object_id`, `month`, `year`
  -> Построение диапазона дат для месяца
  -> Запрос данных объекта из таблицы `firm_objects` по `object_id` и `firm_id`
  -> Если объект не найден, возврат `400 Bad Request`
  -> Запрос финансовых событий из `finance_events` за указанный месяц
  -> Запрос списка сотрудников на объекте из `firm_employees`
  -> Запрос процентов диспетчеров из `dispatcher_attributions`
  -> Формирование сводки по работникам с процентами диспетчеров
  -> Возврат `200 OK` с данными объекта, списком финансовых событий и сводкой работников
-> Обработка `object_activity_presence`:
  -> Валидация наличия `object_id` и `date`
  -> Парсинг `date` в UTC-диапазон суток `[start_at, end_at)`
  -> Чтение активных привязок сотрудников объекта из `firm_employees` и отбор только ролей `worker`, `foreman`
  -> Чтение смен объекта за выбранные сутки из `firm_shifts`
  -> Чтение сделок объекта за выбранные сутки из `firm_deals`
  -> Чтение событий `shift_assign`, `deal_assign` из `object_events` до конца выбранных суток
  -> Батч-чтение `state_json` по `event_id` из `aggregate_state_{firm_id}` для найденных assign-событий
  -> Построение latest assign-map по `shift_id` и `deal_id` через `sequence_number`
  -> Построение latest manual presence-map по `user_id` через `sequence_number`
  -> Группировка смен и сделок по `worker_id` из latest assign-state
  -> Формирование candidate users как объединения `firm_employees.user_id`, `worker_id` из latest `shift_assign/deal_assign` и `user_id` из ручных presence-событий
  -> Чтение событий `obj_enter`, `obj_leave` из `user_events` для candidate users в пределах выбранных суток
  -> Батч-чтение `state_json` по `event_id` из `aggregate_state_{firm_id}` для найденных manual presence-событий
  -> Батч-запрос профилей из `UserProfiles` и процентов из `dispatcher_attributions`
  -> Определение статуса по каждому candidate user:
    -> `foreman`: `present` только по последнему `obj_enter` на этом объекте за день; `finished` по последнему `obj_leave`
    -> `worker`: `present` по активной смене с `opened_at` в текущий день и неистекшим дедлайном, а также по активной сделке в текущий день внутри её временного окна
    -> `worker`: `finished` по терминальному статусу смены/сделки или по последнему `obj_leave`
    -> `worker`: `absent` по назначенной, но ещё не начатой смене/сделке
    -> `worker`: `absent` во всех остальных случаях
  -> Обогащение workers (`user_profile`, `role_label`, `dispatcher_percent`, `last_event_*`, `is_present`, `status`)
  -> Подсчет количества присутствующих работников и общего количества candidate users
  -> Возврат `200 OK` с `workers_present`, `total_workers`, `updated_at`, `workers`
-> Обработка `my_object_presence`:
  -> Запрос последнего события пользователя из `user_events` по `user_id` и типам `OBJ_ENTER`, `OBJ_LEAVE`
  -> Если события отсутствуют, возврат `200 OK` с `is_present=false`, `status=unknown`, `object_id=null`, `object_name=null`
  -> Батч-запрос `state_json` по `event_id` из `aggregate_state_{firm_id}`
  -> Извлечение `object_id`, `last_event_type`, `last_event_at` и статуса присутствия из state
  -> Запрос `object_name` из `firm_objects` по `object_id`, если объект найден в state
  -> Возврат `200 OK` с текущим статусом присутствия вызывающего пользователя
-> Обработка `object_activity_timeline`:
  -> Валидация наличия `object_id` и `date`
  -> Парсинг даты и построение диапазона для суток
  -> Запрос событий из `object_events` за указанную дату
  -> Батч-запрос `state_json` по `event_id` из `aggregate_state_{firm_id}`
  -> Фильтрация событий по `state.object_id == object_id`
  -> Батч-запрос профилей из `UserProfiles` и процентов из `dispatcher_attributions`
  -> Обогащение `timeline_events` полями `event_at`, `user_id`, `status`, `state` и профилями пользователя в state
  -> Формирование `workers_summary` по последнему событию пользователя за дату
  -> Возврат `200 OK` со списком событий, `worker_percents` и `workers_summary`
-> Обработка `finance_turnover`:
  -> Чтение всех объектов фирмы из `firm_objects` с `contract_amount` и `extra_charges_json`
  -> Чтение всех записей `firm_shifts` с полями `shift_id`, `object_id`, `base_payment`, `status`, `created_at`
  -> Чтение всех записей `firm_deals` с полями `deal_id`, `object_id`, `base_payment`, `status`, `created_at`
  -> Чтение событий `shift_assign` и `deal_assign` из `object_events`, начиная с `2020-01-01T00:00:00Z`
  -> Батч-запрос `state_json` по `event_id` из `aggregate_state_{firm_id}` только для найденных `shift_assign` и `deal_assign`
  -> Построение списков целевых `shift_id` и `deal_id` только из прочитанных `firm_shifts` и `firm_deals`
  -> Построение `latest_shift_assign_by_shift_id` и `latest_deal_assign_by_deal_id` только для этих `shift_id/deal_id`, по `object_events.sequence_number`
  -> Расчет денежных агрегатов по объектам:
    -> Для смены учитываются только `firm_shifts.status in {'completed','force_completed'}`
    -> Для смены используются точные поля `firm_shifts.base_payment`, `shift_assign.state.shift_id`, `shift_assign.state.withholding`, `shift_assign.state.dispatcher_percent_snapshot`; `object_id` для финального суммирования берется из канонической строки `firm_shifts`
    -> Выплата по смене считается как `base_payment - % диспетчера`, где `%` берется из `shift_assign.state.dispatcher_percent_snapshot`
    -> Затрата на сотрудника по смене считается из `shift_assign.state.withholding`
    -> Для сделки учитываются только `firm_deals.status in {'archived','completed','force_completed'}`
    -> Для сделки используются точные поля `firm_deals.base_payment`, `deal_assign.state.deal_id`, `deal_assign.state.withholding`; `object_id` для финального суммирования берется из канонической строки `firm_deals`
    -> Выплата по сделке считается как полный `base_payment`, без вычета процента диспетчера
    -> Затрата на сотрудника по сделке считается из `deal_assign.state.withholding`
    -> `turnover_kopeks = contract_amount + extra_charges + shifts + deals + withholds`
    -> `employee_payouts_kopeks = deals + (shifts - dispatcher_percent_snapshot)`
    -> `employee_costs_kopeks = withholds`
    -> `object_costs_kopeks = 0`
    -> `gross_profit_kopeks = 0`
  -> Возврат `200 OK` с денежным summary по всей фирме
-> Обработка `finance_gross_profit`:
  -> Повторное построение фирменного денежного summary по тем же данным, что `finance_turnover`
  -> Возврат `200 OK` с `gross_profit_kopeks = 0`
-> Обработка `finance_objects_summary`:
  -> Валидация `page` и `page_size`
  -> Чтение всех объектов фирмы из `firm_objects` с `contract_amount` и `extra_charges_json`
  -> Чтение всех записей `firm_shifts` с полями `shift_id`, `object_id`, `base_payment`, `status`, `created_at`
  -> Чтение всех записей `firm_deals` с полями `deal_id`, `object_id`, `base_payment`, `status`, `created_at`
  -> Чтение событий `shift_assign` и `deal_assign` из `object_events`, начиная с `2020-01-01T00:00:00Z`
  -> Батч-запрос `state_json` по `event_id` из `aggregate_state_{firm_id}` только для найденных `shift_assign` и `deal_assign`
  -> Построение списков целевых `shift_id` и `deal_id` только из прочитанных `firm_shifts` и `firm_deals`
  -> Построение `latest_shift_assign_by_shift_id` и `latest_deal_assign_by_deal_id` только для этих `shift_id/deal_id`, по `object_events.sequence_number`
  -> Построение `latest_activity_at` по `max(firm_shifts.created_at, firm_deals.created_at)` для каждого `object_id`
  -> Построение денежных агрегатов по каждому объекту:
    -> `contract_amount_kopeks` из `firm_objects.contract_amount`
    -> `extra_charges_total_kopeks` из `firm_objects.extra_charges_json[*].amount`
    -> `shifts_total_kopeks` как сумма `firm_shifts.base_payment` по статусам `completed` и `force_completed`
    -> `deals_total_kopeks` как сумма `firm_deals.base_payment` по статусам `archived`, `completed` и `force_completed`
    -> `withholds_total_kopeks` как сумма `shift_assign.state.withholding + deal_assign.state.withholding`
    -> `employee_payouts_kopeks` как `deal base_payment + (shift base_payment - dispatcher_percent_snapshot из shift_assign)`
    -> `employee_costs_kopeks` как `withholds_total_kopeks`
    -> `object_costs_kopeks = 0`
    -> `gross_profit_kopeks = 0`
    -> `total_kopeks = contract_amount + extra_charges + shifts + deals + withholds`
    -> `shift_assign` и `deal_assign` участвуют в расчете только если `state_json` содержит обязательный идентификатор сущности (`shift_id` или `deal_id`)
    -> Исторические или битые `shift_assign`/`deal_assign`, не содержащие `shift_id`/`deal_id`, пропускаются с логом `analytics_getter.finance_assign.invalid_state_skipped`
    -> Если `shift_assign.state.object_id` или `deal_assign.state.object_id` присутствует и расходится с канонической строкой `firm_shifts/firm_deals`, строка пропускается с логом mismatch; если `object_id` в state отсутствует, суммирование идёт по `firm_shifts.object_id` или `firm_deals.object_id`
    -> Для завершенной смены без валидного `latest_shift_assign_by_shift_id[shift_id]` строка смены пропускается с логом `analytics_getter.finance_shift.assign_missing_skipped`
    -> Для завершенной сделки без валидного `latest_deal_assign_by_deal_id[deal_id]` строка сделки пропускается с логом `analytics_getter.finance_deal.assign_missing_skipped`
  -> Лог `analytics_getter.finance_objects_summary.context_built` пишет размеры прочитанных наборов (`shift_rows`, `deal_rows`, `assign_event_rows`) и количество реально сопоставленных `shift_assign/deal_assign`
  -> Логи `analytics_getter.finance_shift.contribution_applied` и `analytics_getter.finance_deal.contribution_applied` пишут фактически применённые к summary суммы по каждой учтённой смене/сделке
  -> Если `search_query` указан:
    -> Внутренний вызов `vector-search-manager` (action=search, source_table=firm_objects, category=main) с `page` (0-based, конвертируется в 1-based)
    -> Фильтрация `entity_id` из ответа vector-search-manager и сортировка найденных объектов по `latest_activity_at DESC`, затем по `object_name ASC`
    -> `has_next` берется из `vector-search-manager.has_more`
  -> Если `search_query` не указан:
    -> Сортировка полного списка объектов по `latest_activity_at DESC`, затем по `object_name ASC`
    -> Пагинация уже построенного списка объектов по `page/page_size`
    -> `has_next` вычисляется по длине полного списка объектов фирмы
  -> Возврат `200 OK` с `overall`, `page`, `page_size`, `has_next`, `has_prev`, `items`
-> Обработка `employee_attendance_month_summary`:
  -> Валидация `user_id`, `month`, `year` и опционального `object_id`
  -> Построение UTC-окна выбранного месяца `[period_started_at, period_ended_at)`
  -> Чтение строк `firm_shifts` и `firm_deals` в окне месяца
  -> Чтение событий `shift_assign`, `deal_assign`, `shift_start`, `shift_end`, `shift_cancel`, `shift_refuse`, `deal_complete`, `deal_force_end`, `deal_cancel`, `deal_refuse`, `obj_enter`, `obj_leave` из `object_events` в окне месяца и lookback перед окном
  -> Батч-чтение `state_json` по `event_id` из `aggregate_state_{firm_id}` только для найденных object-events
  -> Построение строгих assignment history по `shift_id` и `deal_id` из `shift_assign` и `deal_assign`, без поиска по `user_events`
  -> Отбор только тех смен и сделок, которые относятся к `user_id` по assignment history на момент конкретной строки `firm_shifts/firm_deals`
  -> Построение фактических интервалов:
    -> `shift_start -> terminal shift event`
    -> `obj_enter -> terminal deal event`
    -> `obj_enter -> obj_leave`
    -> Если любая фактическая пара длится больше 24 часов, такая пара считается некорректной attendance-сессией и пропускается с warning-логом
    -> Пересекающиеся фактические интервалы сначала схлопываются в union-отрезки; итоговое `actual_seconds` считает wall-clock время, а не сумму перекрывающихся источников
  -> Построение плановых интервалов:
    -> Для смены `firm_shifts.start_at -> firm_shifts.deadline_at`
    -> Для сделки `obj_enter -> firm_deals.deadline_at`, только если дедлайн сделки попадает в 24 часа после этого `obj_enter`
    -> Для сделки в качестве старта берется последний `obj_enter` на этом объекте, который произошел не позже терминального события именно этой сделки (`deal_complete` / `deal_force_end` / `deal_cancel` / `deal_refuse`), если такое терминальное событие существует
    -> Пересекающиеся плановые интервалы схлопываются в union-отрезки; итоговое `planned_seconds` не дублирует перекрывающиеся окна
  -> Нарезка интервалов по календарным суткам месяца и расчет `calendar_days[*].actual_seconds/planned_seconds`
  -> Фильтрация по `object_id`, если он передан
  -> Подсчет month totals: `actual_seconds`, `planned_seconds`, `unique_objects_count`
  -> Возврат `200 OK` с `objects`, `calendar_days`, `totals`
-> Обработка `employee_attendance_day_details`:
  -> Валидация `user_id`, `date` и опционального `object_id`
  -> Построение UTC-окна выбранных суток `[start_at, end_at)`
  -> Повторное построение attendance dataset только для суток по тем же object-events, `firm_shifts`, `firm_deals` и assignment history, без чтения `user_events`
  -> Отбор и сериализация всех релевантных событий дня по `user_id`: `obj_enter`, `obj_leave`, `shift_start`, терминальные shift/deal события, assign-события только если они нужны для контекста дня
  -> Фильтрация по `object_id`, если он передан
  -> Подсчет day totals: `actual_seconds`, `planned_seconds`, `unique_objects_count`
  -> Возврат `200 OK` с `events` и `totals`
-> Обработка `employee_finance_month_list`:
  -> Валидация `user_id`, `month`, `year`, `page`, `page_size`
  -> Чтение журнала финансовых событий сотрудника за выбранный месяц из `finance_events` и `state_json`
  -> Параллельно чтение полного финансового хвоста сотрудника до конца выбранного периода, `employee_salary` на конец периода и записи из `dispatcher_attributions`
  -> Построение канонического snapshot на конец периода по тем же правилам, что `payroll_queue`: salary remaining, rewards, fines, deals, shifts с вычетом процента диспетчера только из `shift_end`
  -> Возврат paged-журнала в `finance_events`; `total_paid_kopeks` остается агрегатом журнала месяца, `total_pending_kopeks` возвращается как канонический остаток к выплате на конец периода, `month_preview` возвращает готовые totals для превью месяца без дополнительного запроса
-> Обработка `employee_finance_month_total`:
  -> Валидация `user_id`, `month`, `year`
  -> Чтение журнала событий месяца для счетчиков `events_count` и `events_with_amount_count`
  -> Чтение полного финансового хвоста до конца периода, `employee_salary` и `dispatcher_attributions`
  -> Построение канонического snapshot на конец периода по тем же правилам, что `payroll_queue`
  -> Возврат `total_paid_kopeks` как агрегата журнала месяца и `total_pending_kopeks` как канонического остатка к выплате на конец периода
-> Обработка `employee_finance_cash_plan`:
  -> Валидация `user_id` и `as_of`
  -> Чтение финансового хвоста сотрудника для breakdown наличной выплаты: rewards/fines/cash и `employee_salary`
  -> Формирование salary snapshot с `remaining_kopeks` и суммы `total_to_cover_all_kopeks`
  -> Дополнительно чтение текущей `dispatcher_attribution` работника из firms-database
  -> Чтение событий `dispatcher_settlement` и `SHIFT_END` до `as_of`
  -> По последнему `dispatcher_settlement` текущего scope работника определяется нижняя граница нового периода расчета с диспетчером
  -> По прошлым `dispatcher_settlement` восстанавливаются открытые долги работника, уменьшая их на уже записанные `debt_closures`
  -> В ответе `dispatcher_settlement` возвращаются сумма за текущий период, старый долг, общий остаток, ссылки на прошлый расчет и массивы `shifts`/`previous_debts`, из которых UI может собрать частичную выплату диспетчеру
-> Обработка `payroll_queue`:
  -> Валидация `as_of`, `page`, `page_size`, опционального `user_id`
  -> Чтение worker/foreman фирмы из `firm_employees`
  -> Чтение имен из `UserProfiles`, атрибуций из `dispatcher_attributions`, событий из `finance_events` и `state_json` из metadata-system
  -> Для каждого сотрудника построение очереди после последнего `accrual`: fines, rewards, shifts, deals
  -> Чтение `employee_salary_snapshot` на момент `as_of` из `employee_salary`
  -> Чтение полного `cash` до `as_of` для расчета salary remaining по `salary_id`, плюс отдельного period-`cash` после последнего `accrual` для массива `cash` и вычета из части `rewards_fines`
  -> Нормализация `employee_salary_snapshot`: `amount_kopeks` в ответе заменяется на остаток к выплате, дополнительно включаются `source_amount_kopeks`, `paid_kopeks`, `remaining_kopeks`, `overpaid_kopeks`
  -> Для `shift_end` в `totals` и `amount_kopeks` из суммы события вычитается `dispatcher_attribution.percent_snapshot`, если у сотрудника есть атрибуция диспетчера
  -> `deal_complete` учитывается по полной сумме события, без отдельного вычитания процента диспетчера
  -> Отдельные `withheld_shift`/`withhold_accrual` не участвуют в очереди выплат; поле `withholds` остается пустым только для совместимости ответа
  -> Вычисление `deferred_state` по последнему событию `deferred` или `accrual_deferred` после последнего `accrual`; если `accrual` отсутствует, поиск выполняется по всему хвосту событий; статус `is_deferred=true` ставится только если `deferred_until >= as_of`
  -> Перед сравнением `accrual/deferred` сервер нормализует `created_at` из YDB в UTC `datetime`; поддерживаются нативный `datetime`, а также unix timestamp в секундах, миллисекундах и микросекундах, включая строковое представление числа
  -> Пагинация и возврат `ordinary_count`, `deferred_count`, `items`
-> Обработка `payroll_history`:
  -> Разбор режима `day` по `date` или режима `month` по `year` + `month`
  -> Чтение событий `accrual` за выбранный период
  -> Чтение связанных событий `cash` для определения факта выплаты без привязки `deferred` к `accrual`
  -> Определение статуса `accrued` / `paid` для каждого начисления
  -> В month-режиме фильтрация только `paid`
  -> Пагинация и возврат `items` с `accrual_snapshot`
-> Обработка `dispatcher_settlement_queue`:
  -> Валидация `attribution_type`, условного `dispatcher_id`, `as_of`, `page`, `page_size`
  -> Чтение текущих `dispatcher_attributions` фирмы и выделение работников, относящихся к выбранному scope расчета
  -> Чтение событий `dispatcher_settlement` из `finance_events` и их `state_json` из metadata-system
  -> По последнему `dispatcher_settlement` выбранного scope определяется нижняя граница текущего периода расчета
  -> По цепочке прошлых `dispatcher_settlement` восстанавливаются открытые долги работников, уменьшая их на все уже записанные `debt_closures`
  -> Для работников текущего scope читаются `SHIFT_END` после предыдущего расчета; по каждой смене считается точная сумма удержания диспетчера как `gross_amount_kopeks * percent_snapshot / 100`
  -> В ответе по каждому работнику возвращаются:
    -> `current_period_due_kopeks`
    -> `previous_debt_kopeks`
    -> `amount_due_kopeks`
    -> `shifts`
    -> `previous_debts`
  -> Top-level ответ дополнительно возвращает `source_last_settlement_event_id`, `source_last_settlement_created_at`, `period_started_at`, `period_ended_at` и `totals`
-> Обработка исключений: логирование ошибки через `hard_logger` и возврат `500 Internal Server Error`
-> Кэширование runtime-инстанса: credentials из Lockbox и YDB SessionPool сохраняются в глобальных переменных и переиспользуются при warm-start.

На выходе:
-> `200 OK`: успешный ответ с данными аналитики, если запрос обработан успешно
-> `400 Bad Request`: ошибка валидации входных данных, если отсутствуют обязательные поля, невалидный формат данных, объект не найден или неподдерживаемый action
-> `401 Unauthorized`: ошибка авторизации, если отсутствует Bearer токен или JWT токен невалиден
-> `403 Forbidden`: запрет доступа к данным (например, worker пытается запросить данные не своего user_id или dispatcher запрашивает user_id не из своих атрибуций)
-> `426 Upgrade Required`: несовпадение хэшей контракта, если хэши схем не совпадают с ожидаемыми
-> `500 Internal Server Error`: внутренняя ошибка сервера, если не удалось получить SA credentials, подключиться к YDB или возникла неожиданная ошибка

---

Зависимости и окружение
- Утилиты: `utils/__init__.py`, `utils/util_log/yc_logger.py` (YCLogger), `utils/util_ydb/driver.py` (get_session_pool), `utils/util_yc_sa/loader.py` (YcSaLoader), `utils/util_invoke/invoke.py` (invoke_function), `utils/util_contract/schema_hashes.py` (get_expected_schema_hashes), `utils/util_contract/validator.py` (check_contract)
- Переменные окружения:
	- `JWT_SECRET` [[🛡️ auth-gate - CloudFunction функция]]
	- `YDB_ENDPOINT_FIRM_OBJECTS`, `YDB_DATABASE_FIRM_OBJECTS` [[💾 firm-objects-database - База данных YandexDatabase]]
	- `YDB_ENDPOINT_FIRMS`, `YDB_DATABASE_FIRMS` [[💾 firms-database - База данных YandexDatabase]]
	- `YDB_ENDPOINT_EVENTS_LOG`, `YDB_DATABASE_EVENTS_LOG` [[💾 events-log-database - База данных YandexDatabase]]
	- `YDB_ENDPOINT_APPEALS`, `YDB_DATABASE_APPEALS` (нужно для enrichment споров в `worker_fines_list_all_firms`, `employee_absences_disputed`, `employee_absences_month_details`) [[💾 appeals-database - База данных YandexDatabase]]
	- `YDB_ENDPOINT_META`, `YDB_DATABASE_META` (metadata-system: чтение `state_json` из таблиц вида `aggregate_state_{firm_id}`; нужно для `object_finance_history`, `object_activity_presence`, `object_activity_timeline`, `finance_turnover`, `finance_gross_profit`, `finance_objects_summary`, `payroll_queue`, `payroll_history`, `employee_attendance_month_summary`, `employee_attendance_day_details` и action группы dispatcher/worker) [[💾 metadata-system - База данных YandexDatabase]]
	- `YDB_ENDPOINT_NOTICES`, `YDB_DATABASE_NOTICES` (нужно для `employee_finance_month_list`, `employee_finance_month_total`, `employee_finance_cash_plan` и `payroll_queue`: чтение `employee_salary`) [[💾 notices-database - База данных YandexDatabase]]
	- `SA_AUTHKEY_LOCKBOX_SECRET_NAME` [[🗝️  sa-functions-runtime - ключ доступа в lockbox]]
	- `FN_VECTOR_SEARCH_MANAGER` (UID CloudFunction `vector-search-manager`)
	- `VECTOR_SEARCH_MANAGER_SEARCH_REQUEST_SCHEMA_HASH`, `VECTOR_SEARCH_MANAGER_SEARCH_RESPONSE_SCHEMA_HASH` (schema_hashes для action=search в vector-search-manager)
	- `LOG_STREAM_NAME` (необязательная, значение по умолчанию `analytics-getter`)
	- `HARD_LOG_SYMBOL` (необязательная, значение по умолчанию `📊`)
  -> Для `employee_finance_month_list`, `employee_finance_month_total`, `employee_finance_cash_plan` и `payroll_queue`:
    -> Чтение `employee_salary` с фильтром `effective_from <= as_of` и `(deleted_at IS NULL OR deleted_at > as_of)`
    -> Расчет debt по salary-записям, которые действовали на момент `as_of`, даже если их текущий `status` уже `deleted`
