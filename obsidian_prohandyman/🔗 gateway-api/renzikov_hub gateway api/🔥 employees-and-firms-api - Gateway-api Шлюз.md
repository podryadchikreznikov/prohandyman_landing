Идентификатор - d5dc1h8l3tgaa483aj1g
Имя - employees-and-firms-api
Служебный домен - https://d5dc1h8l3tgaa483aj1g.g3ab4gln.apigw.yandexcloud.net

---
### Спецификация

```yaml
openapi: 3.0.0
info:
  title: Employees and Firms Management API
  version: 1.2.0 # Версия обновлена, т.к. добавлен новый метод DELETE FIRM

servers:
  - url: https://d5dc1h8l3tgaa483aj1g.laqt4bj7.apigw.yandexcloud.net

x-yc-apigateway:
  service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
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
    SA_EMPLOYEES_AND_FIRMS_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_AUTH_GATE:
      default: ""
      description: "Cloud Function: auth gate authorizer"
    FN_GET_USER_DATA:
      default: ""
      description: "Cloud Function: get user data"
    FN_CREATE_FIRM:
      default: ""
      description: "Cloud Function: create firm"
    FN_DELETE_FIRM:
      default: ""
      description: "Cloud Function: delete firm"
    FN_INVITE_EMPLOYEE:
      default: ""
      description: "Cloud Function: invite employee"
    FN_EMPLOYEES_MANAGER:
      default: ""
      description: "Cloud Function: employees manager"
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
  /get-user-data:
    get:
      summary: Получить все данные пользователя (инфо, фирмы, задачи) по JWT
      operationId: getUserData
      tags: [User]
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_GET_USER_DATA}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      responses:
        '200': {description: Успешное выполнение.}
        '401': {description: Ошибка авторизации.}
        '404': {description: Пользователь не найден.}
        '500': {description: Внутренняя ошибка.}

  /firms/create:
    post:
      summary: Создать новую фирму
      operationId: createFirm
      tags: [Firms]
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_CREATE_FIRM}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties: {firm_name: {type: string}}
              required: [firm_name]
      responses:
        '201': {description: Фирма успешно создана.}
        '401': {description: Ошибка авторизации.}
        '409': {description: Пользователь уже является членом другой фирмы.}
        '500': {description: Внутренняя ошибка.}

  /firms/{firm_id}/delete:
    post:
      summary: (Высоко рисковая операция) Полное удаление фирмы и всех связанных данных.
      operationId: deleteFirm
      tags: [Firms]
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_DELETE_FIRM}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: {type: string}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties: {}
      responses:
        '200':
          description: Фирма и все связанные данные успешно удалены.
        '400':
          description: Неверные параметры в запросе.
        '403':
          description: Ошибка авторизации или недостаточно прав (только владелец фирмы).
        '412':
          description: Не выполнено одно из предусловий (например, есть активные интеграции или вложения).
        '500':
          description: Внутренняя ошибка сервера.

  /firms/{firm_id}/employees/invite:
    post:
      summary: Пригласить нового сотрудника в фирму по email
      operationId: inviteEmployee
      tags: [Employees]
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_INVITE_EMPLOYEE}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: {type: string}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: {type: string}
              required: [email]
      responses:
        '201': {description: Приглашение успешно отправлено.}
        '403': {description: Недостаточно прав.}
        '409': {description: Пользователь уже работает в этой фирме.}
        '500': {description: Внутренняя ошибка сервера.}

  /employees/create:
    post:
      summary: (УСТАРЕЛО) Добавить существующего пользователя в фирму как сотрудника
      description: "Этот метод является устаревшим. Используйте новый метод /employees/invite."
      operationId: createEmployee
      tags: [Employees, Deprecated]
      x-yc-apigateway:
        context:
          action: CREATE
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_EMPLOYEES_MANAGER}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                firm_id: {type: string}
                email: {type: string}
                roles: {type: array, items: {type: string}}
              required: [firm_id, email]
      responses:
        '201': {description: Сотрудник успешно добавлен.}
        '403': {description: Недостаточно прав.}
        '404': {description: Пользователь для добавления не найден.}
        '409': {description: Пользователь уже работает в этой фирме.}

  /firms/{firm_id}/employees/edit:
    post:
      summary: Редактировать роли или получить информацию о сотруднике
      operationId: editEmployee
      tags: [Employees]
      x-yc-apigateway:
        context:
          action: EDIT
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_EMPLOYEES_MANAGER}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: {type: string}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                user_id_to_edit: {type: string}
                role: {type: string, enum: [ADMIN, EMPLOYEE, MANAGER, SENIOR_FOREMAN, FOREMAN, DISPATCHER, ACCOUNTANT]}
                sub_action: {type: string, enum: [ADD_ROLE, REMOVE_ROLE]}
              required: [user_id_to_edit, role, sub_action]
      responses:
        '200': {description: Успешное выполнение.}
        '400': {description: Неверные параметры.}
        '403': {description: Недостаточно прав.}
        '404': {description: Пользователь не найден.}

  /firms/{firm_id}/employees:
    get:
      summary: Получить сотрудников фирмы
      operationId: getEmployees
      tags: [Employees]
      x-yc-apigateway:
        context:
          action: GET
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_EMPLOYEES_MANAGER}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: {type: string}
        - name: user_id_to_get
          in: query
          required: false
          schema: {type: string}
      responses:
        '200': {description: Успешное выполнение.}
        '400': {description: Неверные параметры.}
        '403': {description: Недостаточно прав.}
        '404': {description: Пользователь не найден.}

  /firms/{firm_id}/employees/delete:
    post:
      summary: Удалить сотрудника из фирмы
      operationId: deleteEmployee
      tags: [Employees]
      x-yc-apigateway:
        context:
          action: DELETE
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_EMPLOYEES_MANAGER}
        service_account_id: ${var.SA_EMPLOYEES_AND_FIRMS_API}
      parameters:
        - name: firm_id
          in: path
          required: true
          schema: {type: string}
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                user_id_to_delete: {type: string}
              required: [user_id_to_delete]
      responses:
        '200': {description: Сотрудник успешно удален.}
        '400': {description: Неверные параметры.}
        '403': {description: Недостаточно прав.}
        '404': {description: Пользователь не найден.}
```

---
### Переменные среды

SA_EMPLOYEES_AND_FIRMS_API = ajepmd4m58cl5aa62iee
FN_AUTH_GATE = d4eko30p260oae7m3rfa
FN_GET_USER_DATA = d4e6qqejob02kq2j8l4l
FN_CREATE_FIRM = d4eoi2t95da1q55doflo
FN_DELETE_FIRM = d4ed3urlbpb3scu7q0rk
FN_INVITE_EMPLOYEE = d4eqvcfq7j6rgrc7ii3q
FN_EMPLOYEES_MANAGER = d4er1pebqu5om94082c3