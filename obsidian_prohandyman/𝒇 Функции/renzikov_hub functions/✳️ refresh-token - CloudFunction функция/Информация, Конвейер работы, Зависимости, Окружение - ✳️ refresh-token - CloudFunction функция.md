
Идентификатор - d4e71eji4nfvf9mi4p09
Описание - Принудительно обновить JWT токен по реквизитам доступа (сброс сессии).
Точка входа - index.handler
Таймаут - 10 сек

---

На входе:
	-> `email` (string, **обязателен если нет phone_number**): Email пользователя.
	-> `phone_number` (string, **обязателен если нет email**): Номер телефона пользователя.
	-> `password` (string, **обязательно**): Пароль пользователя.
Внутренняя работа:
	-> Валидирует входные данные: требуется password и хотя бы один из email/phone_number.
	-> Нормализует phone_number если указан.
    -> Находит в YDB активного пользователя по `email` или `phone_number`.
	-> Сверяет хеш пароля.
	-> Если все верно, принудительно генерирует **новый** JWT токен с email и/или phone_number в claims.
	-> **Перезаписывает** `jwt_token` в базе данных новым значением.
	-> Обновляет `last_login_at`.
На выходе:
	-> `200 OK`: {"token": "<new_jwt_token>"}
    -> `400 Bad Request`: В случае проблем с телом запроса.
	-> `401 Unauthorized`: {"message": "Invalid credentials."}

---
#### Зависимости и окружение
- **Необходимые утилиты**: `utils/*`, `utils/util_ydb/driver.py` 
- **Переменные окружения**:
    - `SA_KEY_JSON` - JSON ключ сервисного аккаунта (поставляется через Lockbox → ENV)
    - `YDB_ENDPOINT`, `YDB_DATABASE` - для `jwt-database` 
    - `JWT_SECRET` - Секретный ключ для JWT