
Идентификатор - [БУДЕТ_СОЗДАН]
Имя - invitation-codes-api
Служебный домен - [БУДЕТ_СОЗДАН]

---
### Спецификация

```yaml
openapi: 3.0.0
info:
  title: Invitation Codes Management API
  version: 1.0.0
  description: API для управления кодами приглашений и запросами на присоединение к фирмам

servers:
  - url: https://[БУДЕТ_СОЗДАН].apigw.yandexcloud.net

x-yc-apigateway:
  service_account_id: ${var.SA_INVITATION_CODES_API}
  cors:
    origin: "*"
    methods:
      - POST
      - GET
      - OPTIONS
    allowedHeaders:
      - Content-Type
      - Authorization
    allowCredentials: true
    maxAge: 3600
  variables:
    SA_INVITATION_CODES_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_AUTH_GATE:
      default: ""
      description: "Cloud Function: auth gate authorizer"
    FN_INVITATION_CODES_MANAGER:
      default: ""
      description: "Cloud Function: invitation codes manager"

paths:
  /codes/create:
    post:
      summary: Создать новый код приглашения
      operationId: createInvitationCode
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: CREATE_CODE
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
              properties:
                firm_id:
                  type: string
                  description: ID фирмы
                max_usage_count:
                  type: integer
                  default: -1
                  description: Максимальное количество использований (-1 = безлимит)
                expires_in_hours:
                  type: integer
                  default: 168
                  description: Срок действия кода в часах
                is_instant:
                  type: boolean
                  default: false
                  description: Моментальное присоединение без подтверждения
                object_id:
                  type: string
                  description: ID объекта стройки
                metadata_json:
                  type: object
                  description: Дополнительная метаинформация
      responses:
        '201':
          description: Код успешно создан
        '400':
          description: Неверные параметры запроса
        '403':
          description: Недостаточно прав
        '500':
          description: Внутренняя ошибка сервера

  /codes/delete:
    post:
      summary: Удалить код приглашения
      operationId: deleteInvitationCode
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: DELETE_CODE
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
                - code_id
              properties:
                firm_id:
                  type: string
                code_id:
                  type: string
      responses:
        '200':
          description: Код успешно удалён
        '403':
          description: Недостаточно прав
        '404':
          description: Код не найден

  /codes/list:
    post:
      summary: Получить список кодов фирмы
      operationId: getInvitationCodes
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: GET_CODES
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
              properties:
                firm_id:
                  type: string
                include_inactive:
                  type: boolean
                  default: false
      responses:
        '200':
          description: Список кодов получен
        '403':
          description: Недостаточно прав

  /codes/instant:
    post:
      summary: Получить краткосрочный код
      operationId: getInstantCode
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: GET_INSTANT_CODE
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
              properties:
                firm_id:
                  type: string
      responses:
        '200':
          description: Краткосрочный код получен
        '403':
          description: Недостаточно прав

  /join:
    post:
      summary: Создать запрос на присоединение по коду
      operationId: joinByCode
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: JOIN_REQUEST
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - code_value
                - firm_id
              properties:
                code_value:
                  type: string
                  description: Значение кода приглашения
                firm_id:
                  type: string
                  description: ID фирмы (для поиска кода)
                dispatcher_id:
                  type: string
                  description: ID диспетчера (опционально)
      responses:
        '201':
          description: Запрос создан или пользователь добавлен
        '400':
          description: Код недействителен или истёк
        '409':
          description: Пользователь уже в фирме

  /requests/list:
    post:
      summary: Получить список запросов на присоединение
      operationId: getJoinRequests
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: GET_REQUESTS
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
                - code_id
              properties:
                firm_id:
                  type: string
                code_id:
                  type: string
                status:
                  type: string
                  enum: [PENDING, APPROVED, REJECTED]
                  description: Фильтр по статусу
      responses:
        '200':
          description: Список запросов получен
        '403':
          description: Недостаточно прав

  /requests/approve:
    post:
      summary: Одобрить запрос на присоединение
      operationId: approveJoinRequest
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: APPROVE_REQUEST
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
                - request_id
                - code_id
              properties:
                firm_id:
                  type: string
                request_id:
                  type: string
                code_id:
                  type: string
      responses:
        '200':
          description: Запрос одобрен
        '403':
          description: Недостаточно прав
        '404':
          description: Запрос не найден

  /requests/reject:
    post:
      summary: Отклонить запрос на присоединение
      operationId: rejectJoinRequest
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITATION_CODES_MANAGER}
        service_account_id: ${var.SA_INVITATION_CODES_API}
        operationContext:
          action: REJECT_REQUEST
      security:
        - BearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required:
                - firm_id
                - request_id
                - code_id
              properties:
                firm_id:
                  type: string
                request_id:
                  type: string
                code_id:
                  type: string
                rejection_reason:
                  type: string
                  description: Причина отклонения
      responses:
        '200':
          description: Запрос отклонён
        '403':
          description: Недостаточно прав
        '404':
          description: Запрос не найден

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        authorizer_result_ttl_in_seconds: 300
        service_account_id: ${var.SA_INVITATION_CODES_API}
```

---
### Описание

API для работы с системой кодов приглашений и запросов на присоединение к фирмам.

#### Основные возможности:
- **Создание кодов приглашений**: Владельцы и администраторы фирм могут создавать коды с настраиваемыми параметрами
- **Краткосрочные коды**: Автоматически обновляемые 10-минутные коды для быстрого присоединения
- **Запросы на присоединение**: Пользователи могут отправлять запросы по коду, которые требуют одобрения
- **Моментальное присоединение**: Коды с флагом `is_instant` добавляют пользователей сразу без подтверждения
- **Управление запросами**: Одобрение или отклонение запросов администраторами фирмы

#### Авторизация:
Все эндпоинты защищены через `auth-gate` функцию. Требуется JWT токен в заголовке `Authorization: Bearer <token>`.

Для операций с кодами (создание, удаление, просмотр) требуется роль OWNER или ADMIN в фирме.
Для создания запроса на присоединение достаточно базовой аутентификации.

#### Переменные окружения:
- `SA_INVITATION_CODES_API`: Service Account для вызова функций
- `FN_AUTH_GATE`: ID функции auth-gate
- `FN_INVITATION_CODES_MANAGER`: ID функции invitation-codes-manager
