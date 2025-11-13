
---
Идентификатор - etnelmllktv71867cu8s
Путь к базе - /ru-central1/b1get3fv6s3logju9ui9/etnelmllktv71867cu8s
Эндпоинт - grpcs://ydb.serverless.yandexcloud.net:2135/?database=/ru-central1/b1get3fv6s3logju9ui9/etnelmllktv71867cu8s

---
# Таблицы
#### Таблица: `users`

| #   | Имя                 | Ключ | Тип              | Описание                                           |
| --- | ------------------- | ---- | ---------------- | -------------------------------------------------- |
| 0   | `user_id`           | PK   | `Utf8`           | Уникальный идентификатор пользователя (UUID).      |
| 1   | `email`             |      | `Utf8`           | Email пользователя (должен быть уникальным).       |
| 2   | `password_hash`     |      | `Utf8`           | Хеш пароля пользователя.                           |
| 3   | `user_name`         |      | `Utf8`           | Имя пользователя.                                  |
| 4   | `created_at`        |      | `Timestamp`      | Время создания записи.                             |
| 5   | `last_login_at`     |      | `Timestamp`      | Время последнего входа.                            |
| 6   | `verification_code` |      | `Utf8`           | Временный код для подтверждения (6-значное число). |
| 7   | `code_expires_at`   |      | `Timestamp`      | Время истечения срока действия кода.               |
| 8   | `is_active`         |      | `Bool`           | Флаг, указывающий, подтвержден ли аккаунт.         |
| 9   | `phone_number`      |      | `Optional<Utf8>` | **(НОВОЕ)** Номер телефона пользователя.           |
| 10  | `jwt_token`         |      | `Optional<Utf8>` | **(НОВОЕ)** Актуальный JWT токен для сессии пользователя. |
