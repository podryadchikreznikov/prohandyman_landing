Идентификатор - d5d62ntg8hfck2psb7e3
Имя - auth-gate-checker
Служебный домен - https://d5d62ntg8hfck2psb7e3.zj2i1qoy.apigw.yandexcloud.net
Каталог - b1gfk08jac021i2pogfv

---
### Спецификация

```yaml
openapi: "3.0.0"
info:
  title: auth-gate-checker
  version: "1.0.1"

x-yc-apigateway:
  service_account_id: ${var.SA_GATE_CHECKER}
  variables:
    SA_GATE_CHECKER:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_AUTH_GATE:
      default: ""
      description: "Cloud Function: auth gate authorizer"
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
  /check:
    get:
      summary: Проверяет JWT токен через функцию-авторизатор (гейт)
      operationId: checkGate
      
      # Это и есть наши "ворота". Перед выполнением основной интеграции
      # API Gateway вызовет эту функцию для проверки прав.
      x-yc-apigateway-authorizer:
        type: function
        # ID функции-авторизатора (auth-gate)
        function_id: ${var.FN_AUTH_GATE}
        tag: ${var.FUNCTION_TAG}

      # Основная интеграция. Это то, что выполнится, ЕСЛИ гейт пропустит запрос.
      x-yc-apigateway-integration:
        type: dummy
        http_code: 200
        http_headers:
          Content-Type: application/json
        content:
          application/json: |
            {
              "status": "ok",
              "message": "Authentication successful. The gate was passed."
            }
            
      responses:
        "200": { description: "Authentication successful" }
        "403": { description: "Authentication failed" }
```

---
### Переменные среды

SA_GATE_CHECKER = aje4dvfc3964dgg1d74t
FN_AUTH_GATE = d4eko30p260oae7m3rfa