
Идентификатор - d4ed3urlbpb3scu7q0rk
Описание - ⛔️ (Высоко рисковая операция) Выполняет полное и необратимое удаление фирмы и всех связанных с ней данных на основе строгих предусловий
Точка входа - index.handler
Таймаут - 10 минут

---

На входе:
	-> `Authorization: Bearer <jwt_token>`: **(Обязательно)** JWT токен пользователя, инициирующего удаление.
	-> Тело запроса:
	    - `firm_id` (string, **обязательно**): ID фирмы, подлежащей удалению.
Внутренняя работа:
	-> Логирует начало процесса удаления для фирмы {firm_id} владельцем {user_id}.
	-> Авторизация и парсинг запроса:
	    -> Извлекает заголовок Authorization, проверяет наличие Bearer токена, иначе AuthError.
	    -> Верифицирует JWT, извлекает user_id, иначе AuthError.
	    -> Парсит тело запроса, извлекает firm_id (обязательно), иначе LogicError.
	-> Подключение к YDB (firms-database), создание пула сессий.
	-> Фаза 1: Проверка предусловий (run_all_checks):
	    -> Проверяет права владельца (_check_owner_permissions): Запрос к Users, проверка наличия записи и roles == ["OWNER"], иначе AuthError.
	    -> Проверяет отсутствие активных интеграций (_check_integrations): Запрос к Firms, парсинг integrations_json, для каждого проверка enabled != true, иначе PreconditionFailedError.
	    -> Логирует успешное прохождение проверок (проверки tasks/clients пропущены - не в текущем проекте).
	-> Фаза 2: Поэтапное удаление (run_all_deletions):
	    -> Логирует пропуск удаления tasks/clients (не в текущем проекте).
	    -> Удаление всех сотрудников кроме владельца (_delete_all_employees): Вызов employee-manager с `{"firm_id": firm_id}` для получения списка, фильтр `user_id != owner_id`, затем удаление каждого вызовом employee-manager с `{"firm_id": firm_id, "user_id_to_delete": ...}`; логирует прогресс.
	    -> Удаление записи тарифов (_delete_tariffs_and_storage_record): Подключение к tariffs DB, DELETE FROM tariffs_and_storage WHERE firm_id; логирует.
	    -> Финальное удаление записей фирмы (_delete_firm_records): Подключение к firms DB, в транзакции DELETE FROM Firms WHERE firm_id, DELETE FROM Users WHERE user_id=owner_id AND firm_id; логирует.
	-> Логирует успешное завершение удаления.
	-> Обработка исключений: Логирует ошибки, возвращает соответствующий статус (403 для AuthError, 400 для LogicError, 412 для PreconditionFailedError, 500 для других).
На выходе:
	-> `200 OK`: `{"message": "Firm and all associated data successfully deleted."}`
	-> `400 Bad Request`: Отсутствует или некорректен `firm_id` в теле запроса.
	-> `403 Forbidden`: Токен недействителен или у пользователя нет прав `OWNER`.
	-> `412 Precondition Failed`: Одно из предусловий (по интеграциям) не выполнено.
	-> `500 Internal Server Error`: Внутренняя ошибка сервера в процессе выполнения.

---

Зависимости и окружение

Необходимые утилиты: `utils/util_http/request.py` (parse_event), `utils/util_http/response.py` (json_response/bad_request/forbidden/server_error), `utils/util_ydb/driver.py` (get_session_pool, get_driver), `utils/util_invoke/invoke.py` (invoke_function), `utils/util_crypto/jwt_tokens.py` (verify_jwt), `invoke_utils.py`
Переменные окружения:
    *   `YDB_ENDPOINT_FIRMS`, `YDB_DATABASE_FIRMS`
    *   `YDB_ENDPOINT_TARIFFS_AND_STORAGE`, `YDB_DATABASE_TARIFFS_AND_STORAGE`
    *   `FUNCTION_ID_EMPLOYEE_MANAGER`
    *   `SA_KEY_FILE`
    *   `JWT_SECRET`