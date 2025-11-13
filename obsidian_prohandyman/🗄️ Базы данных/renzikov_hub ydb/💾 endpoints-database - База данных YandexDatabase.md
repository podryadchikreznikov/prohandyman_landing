Идентификатор - etnk8j43kos5461f07gq
Путь к базе - /ru-central1/b1get3fv6s3logju9ui9/etnk8j43kos5461f07gq
Эндпоинт - grpcs://ydb.serverless.yandexcloud.net:2135/?database=/ru-central1/b1get3fv6s3logju9ui9/etnk8j43kos5461f07gq

---
# Таблицы
В данной базе данных хранятся подписки пользователей на уведомления с разных платформ.

#### Таблица: `UserEndpoints`

| # | Имя | Ключ | Тип | Описание |
| :-- | :--- | :--- | :--- | :--- |
| 0 | **`push_token_hash`** | PK | **`Utf8`** | **(ИЗМЕНЕНО)** Хеш от `push_token` (SHA256). Является первичным ключом. Используем хеш, чтобы избежать проблем с длиной ключа. |
| 1 | `user_id` | | `Utf8` | ID пользователя, которому принадлежит подписка. |
| 2 | `platform` | | `Utf8` | Тип платформы: `WEB` или `RUSTORE`. |
| 3 | `push_token` | | `Utf8` | Исходный токен подписки (JSON-строка для WEB, токен устройства для RUSTORE). |
| 4 | `endpoint_arn` | | `Optional<Utf8>` | ARN, выданный Yandex CNS. **Заполняется только для платформы `WEB`**. |
| 5 | `is_enabled` | | `Bool` | Флаг, отражающий, активна ли подписка. |
| 6 | `device_info_json` | | `Json` | JSON-объект с информацией об устройстве. |
| 7 | `created_at` | | `Timestamp` | Время создания записи. |
| 8 | `updated_at` | | `Timestamp` | Время последнего обновления записи. |

---
#### YQL для управления таблицей

**YQL для создания таблицы:**
```yql
CREATE TABLE `UserEndpoints` (
    push_token_hash Utf8,
    user_id Utf8,
    platform Utf8,
    push_token Utf8,
    endpoint_arn Utf8,
    is_enabled Bool,
    device_info_json Json,
    created_at Timestamp,
    updated_at Timestamp,
    PRIMARY KEY (push_token_hash),
    INDEX user_id_index GLOBAL ON (user_id)
);
```