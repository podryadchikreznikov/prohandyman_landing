
Идентификатор - d4em90c6ufbfiss95ag4
Описание - 🔗 Управление JSON-интеграциями компании: получить (`GET`), добавить/обновить (`UPSERT`), удалить (`DELETE`).
Точка входа - index.handler
Таймаут - 10 сек

---
### Конвейер работы
На входе:
	-> `Authorization: Bearer <jwt_token>`: JWT любого авторизованного пользователя.
	-> `X-Forwarded-Authorization: Bearer <jwt_token>` (служебный вход, передается внутренними сервисами).
	-> `firm_id` (string, **обязательно**): ID фирмы, с которой работаем.
	-> `action` (string, **обязательно**): `GET`, `UPSERT`, `DELETE`.
	-> `payload` (object, опц.) — JSON-объект с новыми/обновлёнными интеграциями для `UPSERT`.
	-> `integration_keys` (array<string>, опц.) — список ключей, которые нужно удалить при `DELETE`.

Внутренняя работа:
	-> Установка логирования: logging.basicConfig(level=logging.INFO)
	-> Авторизация:
		-> Получение headers из event.
		-> Поиск auth_header в 'x-forwarded-authorization' или 'authorization'.
		-> Если не начинается с 'Bearer ', raise AuthError("Unauthorized")
		-> Извлечение token, auth_utils.verify_jwt(token), получение user_id. Если не, raise AuthError("Invalid token")
	-> Парсинг тела запроса: request_parser.parse_request_body(event)
		-> Получение firm_id и action. Если не все, raise LogicError("firm_id and action are required")
	-> Подключение к YDB: ydb_utils.get_driver_for_db(os.environ['YDB_ENDPOINT_FIRMS'], os.environ['YDB_DATABASE_FIRMS']), создание ydb.SessionPool(driver)
	-> В транзакции (pool.retry_operation_sync(txn)):
		-> Проверка членства и роли: _check_membership_and_role(session, user_id, firm_id)
			-> Подготовка и выполнение запроса: SELECT roles FROM Users WHERE user_id = $uid AND firm_id = $fid
			-> Если нет rows, return (False, False)
			-> Парсинг roles из json.loads(roles or '[]'), проверка наличия 'OWNER' или 'ADMIN'
			-> Если не член, raise AuthError("User is not a member of the specified firm")
		-> Маршрутизация по action:
			-> Если 'GET':
				-> _get_integrations(session, firm_id):
					-> Подготовка и выполнение: SELECT integrations_json FROM Firms WHERE firm_id = $fid
					-> Если нет rows, raise NotFoundError("Firm not found")
					-> return json.loads(integrations_json or '{}')
				-> return {"statusCode": 200, "body": json.dumps({"integrations": integrations})}
			-> Если 'UPSERT':
				-> Если не is_admin_or_owner, raise AuthError("Admin or Owner rights required for UPSERT")
				-> Получение payload = data.get('payload'), если не isinstance(payload, dict), raise LogicError("payload must be an object for UPSERT")
				-> _upsert_integrations(session, firm_id, payload):
					-> current = _get_integrations(session, firm_id)
					-> _deep_merge_dict(current, payload)  # Рекурсивный мердж словарей
					-> new_json = json.dumps(current)
					-> now = datetime.datetime.now(pytz.utc)
					-> Подготовка и выполнение: UPDATE Firms SET integrations_json = $data, updated_at = $now WHERE firm_id = $fid
				-> return {"statusCode": 200, "body": json.dumps({"message": "Integrations updated"})}
			-> Если 'DELETE':
				-> Если не is_admin_or_owner, raise AuthError("Admin or Owner rights required for DELETE")
				-> Получение keys = data.get('integration_keys') or [], если не isinstance(keys, list), raise LogicError("integration_keys must be a list for DELETE")
				-> _delete_integrations(session, firm_id, keys):
					-> current = _get_integrations(session, firm_id)
					-> for k in keys: current.pop(k, None)
					-> new_json = json.dumps(current)
					-> now = datetime.datetime.now(pytz.utc)
					-> Подготовка и выполнение: UPDATE Firms SET integrations_json = $data, updated_at = $now WHERE firm_id = $fid
				-> return {"statusCode": 200, "body": json.dumps({"message": "Integrations deleted"})}
			-> Иначе: raise LogicError("Invalid action")
	-> Обработка исключений:
		-> AuthError as e: return {"statusCode": 401 if 'Unauthorized' in str(e) else 403, "body": json.dumps({"message": str(e)})}
		-> LogicError as e: return {"statusCode": 400, "body": json.dumps({"message": str(e)})}
		-> NotFoundError as e: return {"statusCode": 404, "body": json.dumps({"message": str(e)})}
		-> Exception as e: logging.error(f"Critical error in edit-integrations: {e}", exc_info=True), return {"statusCode": 500, "body": json.dumps({"message": "Internal Server Error"})}
На выходе:
	-> `200 OK` (GET): `{ "integrations": { ... } }`
	-> `200 OK` (UPSERT): `{ "message": "Integrations updated" }`
	-> `200 OK` (DELETE): `{ "message": "Integrations deleted" }`
	-> `400 Bad Request`: Неверные параметры.
	-> `401 Unauthorized`: Невалидный/отсутствует JWT.
	-> `403 Forbidden`: Недостаточно прав.
	-> `404 Not Found`: Фирма не найдена.
	-> `500 Internal Server Error`: Необработанная ошибка сервера.

---
#### Зависимости и окружение
- **Необходимые утилиты**: `utils/auth_utils.py`, `utils/ydb_utils.py`, `utils/request_parser.py`, `utils/util_yc_sa/*`
- **Переменные окружения**:
	- `YDB_ENDPOINT_FIRMS`, `YDB_DATABASE_FIRMS`
	- `YC_LOCKBOX_SECRET_ID` - secret_id Lockbox с authorized key JSON
	- `YC_LOCKBOX_VERSION_ID` - опционально, версия секрета
	- `YC_LOCKBOX_KEY_FIELD` - опционально, имя поля в секрете (по умолчанию key.json)
	- `JWT_SECRET`