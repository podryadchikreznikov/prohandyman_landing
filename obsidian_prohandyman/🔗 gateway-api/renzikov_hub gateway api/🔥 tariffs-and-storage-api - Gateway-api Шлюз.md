
Идентификатор - d5do791qvip791842fm4
Имя - tariffs-and-storage-api
Служебный домен - https://d5do791qvip791842fm4.fary004x.apigw.yandexcloud.net

---
### Спецификация

```yaml
openapi: 3.0.0
info:
  title: Tariffs and Storage API
  version: 1.0.0
servers:
  - url: https://d5do791qvip791842fm4.sk0vql13.apigw.yandexcloud.net

x-yc-apigateway:
  service_account_id: ${var.SA_TARIFFS_AND_STORAGE_API}
  cors:
    origin: "*"
    methods:
      - "POST"
      - "OPTIONS"
    allowedHeaders:
      - "Content-Type"
      - "Authorization"
    allowCredentials: true
    maxAge: 3600
  variables:
    SA_TARIFFS_AND_STORAGE_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_AUTH_GATE:
      default: ""
      description: "Cloud Function: auth gate authorizer"
    FN_TARIFFS_MANAGER:
      default: ""
      description: "Cloud Function: tariffs manager"
    FN_INTEGRATIONS_MANAGER:
      default: ""
      description: "Cloud Function: integrations manager"
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
  /firms/{firm_id}/tariffs/manage:
    post:
      summary: Универсальный метод для управления тарифами и хранилищем
      description: |
        Позволяет выполнять следующие операции:
        - GET_RECORD: Получить запись о тарифе и хранилище для фирмы.
        - UPDATE_JSON: Атомарно обновить данные в JSON-полях.
        - CLEAR_JSON: Очистить JSON-поля.
        - GET_UPLOAD_URL: Получить pre-signed URL для загрузки файла.
        - GET_DOWNLOAD_URL: Получить pre-signed URL для скачивания файла.
        - CONFIRM_UPLOAD: Подтвердить загрузку и обновить квоту.
        - DELETE_FILE: Удалить файл из хранилища.
      operationId: manageTariffsAndStorage
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_TARIFFS_MANAGER}
        service_account_id: ${var.SA_TARIFFS_AND_STORAGE_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                action:
                  type: string
                  enum: [GET_RECORD, UPDATE_JSON, CLEAR_JSON, GET_UPLOAD_URL, GET_DOWNLOAD_URL, CONFIRM_UPLOAD, DELETE_FILE]
                
                # Поля для UPDATE_JSON
                target_json_field:
                  type: string
                  description: "Имя поля для обновления. Обязательно для action: UPDATE_JSON."
                updates:
                  type: object
                  description: "Объект с обновлениями. Обязательно для action: UPDATE_JSON."

                # Поля для CLEAR_JSON
                fields_to_clear:
                  type: array
                  items:
                    type: string
                  description: "Список полей для очистки. Обязательно для action: CLEAR_JSON."

                # Поля для GET_UPLOAD_URL
                filename:
                  type: string
                  description: "Имя файла. Обязательно для action: GET_UPLOAD_URL."
                filesize:
                  type: integer
                  description: "Размер файла в байтах. Обязательно для action: GET_UPLOAD_URL."
                  
                # Поля для GET_DOWNLOAD_URL, DELETE_FILE, CONFIRM_UPLOAD
                file_key:
                  type: string
                  description: "Ключ файла в S3. Обязательно для action: DELETE_FILE, GET_DOWNLOAD_URL, CONFIRM_UPLOAD."
              required:
                - action
      responses:
        '200':
          description: Успешное выполнение.
        '400':
          description: Неверные параметры в запросе.
        '403':
          description: Ошибка авторизации или недостаточно прав.
        '404':
          description: Ресурс не найден (например, запись о фирме или файл).
        '413':
          description: Квота на хранилище превышена.
        '500':
          description: Внутренняя ошибка сервера.
  /firms/{firm_id}/integrations:
    post:
      summary: Управление интеграциями фирмы
      description: |
        Позволяет выполнять следующие операции:
        - GET: Получить текущий JSON интеграций фирмы.
        - UPSERT: Добавить новые / обновить существующие ключи интеграций.
        - DELETE: Удалить указанные интеграции по ключам.
      operationId: manageFirmIntegrations
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INTEGRATIONS_MANAGER}
        service_account_id: ${var.SA_TARIFFS_AND_STORAGE_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: { type: string }
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                action:
                  type: string
                  enum: [GET, UPSERT, DELETE]
                payload:
                  type: object
                  description: "JSON-объект интеграций для action: UPSERT."
                integration_keys:
                  type: array
                  items:
                    type: string
                  description: "Список ключей для удаления. Обязательно для action: DELETE."
              required:
                - action
      responses:
        '200':
          description: Успешное выполнение.
        '400':
          description: Неверные параметры запроса.
        '403':
          description: Ошибка авторизации или недостаточно прав.
        '404':
          description: Фирма не найдена.
        '500':
          description: Внутренняя ошибка сервера.
```

---
### Переменные среды

SA_TARIFFS_AND_STORAGE_API = aje4dvfc3964dgg1d74t
FN_AUTH_GATE = d4eko30p260oae7m3rfa
FN_TARIFFS_MANAGER = d4eldr0g66rsnknt8cvf
FN_INTEGRATIONS_MANAGER = d4em90c6ufbfiss95ag4