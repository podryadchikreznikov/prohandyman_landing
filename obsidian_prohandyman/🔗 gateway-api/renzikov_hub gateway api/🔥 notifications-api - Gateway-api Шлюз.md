Идентификатор - d5dqe519ci8oku6g0075
Имя - notifications-api
Служебный домен - https://d5dqe519ci8oku6g0075.pdkwbi1w.apigw.yandexcloud.net

---
### Спецификация

```yaml
openapi: 3.0.0
info:
  title: Notifications API
  version: 1.2.0
  description: |
    Единый API для управления push-подписками и уведомлениями.
    
    **Ключевые изменения в версии 1.2.0:**
    - Метод DELETE /subscriptions теперь работает по `push_token` в теле запроса, а не по ARN в пути.
    - Удален неиспользуемый эндпоинт GET /subscriptions/{endpointArn}.

servers:
  - url: https://d5dqe519ci8oku6g0075.bixf7e87.apigw.yandexcloud.net

x-yc-apigateway:
  service_account_id: ${var.SA_NOTIFICATIONS_API}
  cors:
    origin: "*"
    methods:
      - "GET"
      - "POST"
      - "DELETE"
      - "OPTIONS"
    allowedHeaders:
      - "Content-Type"
      - "Authorization"
    allowCredentials: true
    maxAge: 3600
  variables:
    SA_NOTIFICATIONS_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_AUTH_GATE:
      default: ""
      description: "Cloud Function: auth gate authorizer"
    FN_ENDPOINTS_MANAGER:
      default: ""
      description: "Cloud Function: endpoints manager"
    FN_NOTICES_MANAGER:
      default: ""
      description: "Cloud Function: notices manager"
    FUNCTION_TAG:
      default: "$latest"
      description: "Function version tag"

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

security:
  - bearerAuth: []

paths:
  # --- Ресурсы для управления подписками (Subscriptions) ---
  /subscriptions:
    get:
      summary: Получить список всех подписок пользователя
      operationId: getSubscriptionsList
      tags: [Subscriptions]
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_ENDPOINTS_MANAGER}
        service_account_id: ${var.SA_NOTIFICATIONS_API}
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: GET_LIST
        caching: 
          enabled: false
    post:
      summary: Добавить новую подписку на уведомления
      operationId: addSubscription
      tags: [Subscriptions]
      x-yc-apigateway-authorizer:
        type: function
        function_id: d4eko30p260oae7m3rfa
        tag: $latest
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                push_token:
                  type: string
                  description: "JSON-строка для Web Push или токен устройства для RuStore."
                device_info:
                  type: object
                  description: "Необязательная информация об устройстве."
              required: [push_token]
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: d4e6pc9kpgijmt3ii2v9 # -> endpoints-manager
        service_account_id: aje4dvfc3964dgg1d74t
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: ADD
    delete:
      summary: Удалить подписку по push-токену
      operationId: deleteSubscriptionByToken
      tags: [Subscriptions]
      x-yc-apigateway-authorizer:
        type: function
        function_id: d4eko30p260oae7m3rfa
        tag: $latest
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                push_token:
                  type: string
                  description: "Токен подписки, которую необходимо удалить."
              required: [push_token]
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: d4e6pc9kpgijmt3ii2v9 # -> endpoints-manager
        service_account_id: aje4dvfc3964dgg1d74t
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: DELETE
  
  # --- Ресурсы для управления уведомлениями (Notices) ---
  /notices:
    get:
      summary: Получить список уведомлений (новых или архивных)
      operationId: getNoticesList
      tags: [Notices]
      x-yc-apigateway-authorizer:
        type: function
        function_id: d4eko30p260oae7m3rfa
        tag: $latest
      parameters:
        - name: page
          in: query
          schema: { type: integer, default: 0 }
        - name: get_archived
          in: query
          schema: { type: boolean, default: false }
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: d4e3v8k2iijejj8du1t1 # -> notices-manager
        service_account_id: aje4dvfc3964dgg1d74t
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: GET
        caching: 
          enabled: false

  /notices/{noticeId}:
    parameters:
      - name: noticeId
        in: path
        required: true
        schema: { type: string }
    get:
      summary: Получить одно уведомление по ID
      operationId: getNoticeById
      tags: [Notices]
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_NOTICES_MANAGER}
        service_account_id: ${var.SA_NOTIFICATIONS_API}
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: GET
          
  /notices/archive:
    post:
      summary: Архивировать одно уведомление
      operationId: archiveNotice
      tags: [Notices]
      x-yc-apigateway-authorizer:
        type: function
        function_id: d4eko30p260oae7m3rfa
        tag: $latest
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties: { notice_id: { type: string } }
              required: [notice_id]
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: d4e3v8k2iijejj8du1t1 # -> notices-manager
        service_account_id: aje4dvfc3964dgg1d74t
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: ARCHIVE

  /notices/mark-as-delivered:
    post:
      summary: Пометить уведомления как доставленные
      operationId: markAsDelivered
      tags: [Notices]
      x-yc-apigateway-authorizer:
        type: function
        function_id: d4eko30p260oae7m3rfa
        tag: $latest
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                notice_ids: { type: array, items: { type: string } }
              required: [notice_ids]
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: d4e3v8k2iijejj8du1t1 # -> notices-manager
        service_account_id: aje4dvfc3964dgg1d74t
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: MARK_AS_DELIVERED

  # --- Действие по отправке уведомлений ---
  /send-notification:
    post:
      summary: Отправить уведомление пользователю
      description: |
        Отправляет push-уведомление на все активные устройства указанного пользователя.
        **Предназначен для вызова внутренними сервисами сервера, а не конечным пользователем.**
      operationId: sendNotification
      tags: [Actions]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                user_id_to_notify: { type: string }
                payload:
                  type: object
                  properties:
                    title: { type: string }
                    body: { type: string }
                    icon: { type: string }
                  required: [title, body]
              required: [user_id_to_notify, payload]
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_ENDPOINTS_MANAGER}
        service_account_id: ${var.SA_NOTIFICATIONS_API}
        # ИЗМЕНЕНО: payload_format_version удален
        context:
          action: SEND
```

---
### Переменные среды

SA_NOTIFICATIONS_API = aje4dvfc3964dgg1d74t
FN_AUTH_GATE = d4eko30p260oae7m3rfa
FN_ENDPOINTS_MANAGER = d4e6pc9kpgijmt3ii2v9
FN_NOTICES_MANAGER = d4e3v8k2iijejj8du1t1