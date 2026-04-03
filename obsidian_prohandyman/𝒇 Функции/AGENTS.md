## Auth And Invocation Rules

Это обязательные правила для всех правок в `obsidian_balansoved/𝒇 Фнукции`.

### Что не ломать

- Не ломать `access_policy.json`. Это внешний периметр доступа для HTTP/WS через gateway.
- Не ломать `function_types_registry`. Это источник истины для `real_function_id`, `invoke_path_template`, `action_value`, `request_contract_hash`, `response_contract_hash`.
- Не ломать механизм `426 OUTDATED_CLIENT_SCHEMA`.
- Не превращать `event_registry.metadata_json` в свалку transport/auth полей.
- Не ломать таблицы `event_registry`, `event_execution_registry`, `ws_connections`, `client_sessions`, `firm_users`.

### Канон

- Внешний HTTP/WS запрос идет только через `access-gate`.
- Внутренний вызов `function -> function` идет только как service-to-service через IAM.
- Queue и scheduled flow не имитируют внешний пользовательский запрос.
- Бизнес-функции читают identity только из нормализованного context, а не из сырого токена.

### Внешние запросы

- `access-gate` проверяет JWT или client session token и кладет в `authorizer.context` нормализованный identity context.
- Бизнес-функции не валидируют JWT повторно и не парсят bearer token повторно.
- Минимум для employee context: `auth_type`, `principal_type`, `principal_id`, `user_id`, `email`, `firm_id`, `role_type`.
- Минимум для client context: `auth_type`, `principal_type`, `principal_id`, `client_id`, `firm_id`, `client_session_id`, `role_type`.

### Внутренние вызовы

- Внутренний вызов не тащит JWT пользователя дальше по цепочке.
- Внутренний вызов не подделывает внешний `authorizer`.
- Для internal call использовать единый `internal_invocation_context`.
- Минимум полей: `auth_type=internal_service`, `service_name`, `trace_id`, `execution_id?`, `firm_id?`, `initiator_user_id?`, `initiator_role_type?`, `source_type?`, `source_id?`.
- `initiator_*` это только audit/business context, а не доказательство прав.
- Нельзя ставить `role_type = owner` по умолчанию.

### Queue и scheduled events

- Queue сообщение содержит только job envelope и бизнес payload.
- В queue запрещены JWT, `Authorization`, сырые `headers`, `query`, `path`, fake `authorizer`.
- `event_registry.metadata_json` хранит только бизнес-данные.
- В `metadata_json` запрещены поля подмены transport/auth: `__authorizer`, `__headers`, `__query`, `__path`, `__raw_path`, `__invoke_path`.
- Для scheduled flow путь вызова, `action` и contract hashes определяет только `function_types_registry`.
- Scheduled и queue consumer исполняются как system/service flow.

### WS

- WS auth только на `CONNECT`.
- После `CONNECT` identity хранится в `ws_connections`.
- `MESSAGE` и broadcast не валидируют токен повторно.
- Весь доступ после `CONNECT` идет через `connection_id` и сохраненный context.

### Что обязано остаться внутри функций

- Domain checks.
- Ownership checks.
- Resource consistency checks.
- Проверки `firm_id`, `client_id`, `user_id`, `responsible_user_id`, статусов и бизнес-ограничений.
- Проверка, что internal endpoint вызывается только из разрешенного service flow.

### Что запрещено

- Повторно валидировать JWT в бизнес-функции после `access-gate`.
- Повторно разбирать bearer token в employee-only функциях.
- Подделывать `authorizer.user_id` или `authorizer.role_type`.
- Давать fallback роль `"owner"`.
- Давать fallback transport path/query/header для внутренних вызовов.
- Хранить transport/auth override в бизнес metadata.
