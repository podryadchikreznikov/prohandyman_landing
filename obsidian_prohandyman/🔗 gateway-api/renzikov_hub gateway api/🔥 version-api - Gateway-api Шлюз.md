Идентификатор - d5d2vigu6hojb3u0fthu
Имя - version-api
Служебный домен - https://d5d2vigu6hojb3u0fthu.8wihnuyr.apigw.yandexcloud.net

---
### Спецификация

```yaml
openapi: 3.0.0
info:
  title: Version API
  version: 1.0.0
servers:
  - url: https://d5d2vigu6hojb3u0fthu.lievo6ut.apigw.yandexcloud.net
  - url: wss://d5d2vigu6hojb3u0fthu.lievo6ut.apigw.yandexcloud.net

x-yc-apigateway:
  service_account_id: ${var.SA_VERSION_API}
  cors:
    origin: "*"
    methods:
      - "GET"
      - "OPTIONS"
    allowedHeaders:
      - "Content-Type"
    allowCredentials: false
    maxAge: 3600
  variables:
    SA_VERSION_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    CURRENT_VERSION:
      type: string
      default: "0.1.31+1" 

paths:
  /current:
    get:
      summary: Получить актуальную версию приложения
      description: |
        Возвращает строку текущей версии в формате SemVer с номером сборки
        (например, 1.0.0+1, 2.1.3+4 или 0.0.1).
      operationId: getCurrentVersion
      tags:
        - Version
      x-yc-apigateway-integration:
        type: dummy
        http_code: 200
        http_headers:
          Content-Type: application/json
        content:
          # ПРАВИЛЬНЫЙ СИНТАКСИС СОГЛАСНО ДОКУМЕНТАЦИИ
          application/json: '{ "version": "${var.CURRENT_VERSION}" }'
      responses:
        '200':
          description: Текущая версия успешно получена.
          content:
            application/json:
              schema:
                type: object
                properties:
                  version:
                    type: string
                    description: "Строка версии приложения в формате SemVer+build."
                    example: "1.0.0+1"
              examples:
                success:
                  summary: Пример успешного ответа
                  value:
                    version: "2.1.3+4"
        '500':
          description: Внутренняя ошибка сервиса или зависимостей.
```

---
### Переменные среды

SA_VERSION_API = aje4dvfc3964dgg1d74t
CURRENT_VERSION = 0.1.31+1
