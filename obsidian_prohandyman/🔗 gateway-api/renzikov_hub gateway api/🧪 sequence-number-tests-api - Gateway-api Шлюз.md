Идентификатор - TBD (создаётся при деплое)
Имя - sequence-number-tests-api
Служебный домен - https://tbd-seq-tests.apigw.yandexcloud.net (после публикации заменить на фактический)
Назначение - тестовые точки входа для функции ✳️🔢 sequence-number-generator

---
### Спецификация

```yaml
openapi: "3.0.0"
info:
  title: sequence-number-tests-api
  version: "0.1.0"
  description: |
    Минимальный шлюз для ручных и автоматизированных тестов функции sequence-number-generator.

x-yc-apigateway:
  service_account_id: ${var.SA_TESTS_API}
  cors:
    origin: "*"
    methods: [POST, OPTIONS]
    allowedHeaders: ["Content-Type", "X-Correlation-Id"]
    credentials: false
    maxAge: 600
  variables:
    SA_TESTS_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_SEQUENCE_NUMBER_GENERATOR:
      default: ""
      description: "Cloud Function: sequence-number-generator"

paths:
  /sequence-number:
    post:
      summary: Создаёт (или возвращает) последовательность для произвольного агрегата
      operationId: createSequenceNumber
      tags: [SequenceNumber]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                entity_type:
                  type: string
                  description: "Тип агрегата (например, deal, shift, invoice)"
                uuid:
                  type: string
                  format: uuid
                  description: "UUID агрегата"
              required: [entity_type, uuid]
      responses:
        "200": { description: "Функция вернула статус NEW/EXISTING и очередной номер" }
        "400": { description: "Неверное тело запроса либо некорректный UUID" }
        "500": { description: "Ошибка функции или YDB" }
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_SEQUENCE_NUMBER_GENERATOR}
        tag: "$latest"

  /sequence-number/tests/new:
    post:
      summary: Сервисный positive-сценарий для smoke-тестов (ожидаем статус NEW)
      operationId: sequenceNumberNewFixture
      tags: [SequenceNumberTests]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                entity_type:
                  type: string
                  description: "Можно не передавать — по умолчанию test-seq"
                uuid:
                  type: string
                  format: uuid
                  description: "UUID агрегата; при каждом запуске лучше использовать новый"
              required: [uuid]
      responses:
        "200": { description: "Возвращает sequence_number со статусом NEW" }
        "400": { description: "Пустой/невалидный UUID" }
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_SEQUENCE_NUMBER_GENERATOR}
        tag: "$latest"
        context:
          test_case: "positive-new"
          default_entity_type: "test-seq"

  /sequence-number/tests/existing:
    post:
      summary: Повторный вызов с теми же значениями (ожидаем статус EXISTING)
      operationId: sequenceNumberExistingFixture
      tags: [SequenceNumberTests]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                entity_type:
                  type: string
                  description: "Тип агрегата; должен совпадать с предыдущим вызовом"
                uuid:
                  type: string
                  format: uuid
                  description: "UUID агрегата; должен совпадать с предыдущим вызовом"
              required: [entity_type, uuid]
      responses:
        "200": { description: "Получаем sequence_number со статусом EXISTING" }
        "400": { description: "Пустые поля запроса" }
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_SEQUENCE_NUMBER_GENERATOR}
        tag: "$latest"
        context:
          test_case: "repeat-existing"
          advisory: "Перед повтором сначала вызовите /sequence-number/tests/new"

  /sequence-number/tests/invalid-uuid:
    post:
      summary: Negative-сценарий — демонстрирует 400 Bad Request
      operationId: sequenceNumberInvalidUuid
      tags: [SequenceNumberTests]
      requestBody:
        required: false
      responses:
        "400": { description: "Функция отработала валидацию UUID" }
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_SEQUENCE_NUMBER_GENERATOR}
        tag: "$latest"
        context:
          test_case: "invalid-uuid"
          override_body:
            entity_type: "test-seq"
            uuid: "not-a-uuid"
```

---
### Переменные среды

SA_VERSION_API = aje4dvfc3964dgg1d74t
FN_SEQUENCE_NUMBER_GENERATOR = <ID функции ✳️🔢 sequence-number-generator>  
