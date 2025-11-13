Идентификатор - d5dii40lrt3h821egn3i
Имя - callback-request-api
Служебный домен - https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net
Служебный домен для WebSocket - https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net
Статус - Active
Дата создания - 13.11.2025, в 18:48
Таймаут обработки запроса - 5 минут

---
### Спецификация

```yaml
openapi: 3.0.0
info:
  title: Callback Request API
  version: 1.0.0
  description: |
    API принимает заявки на обратный звонок. Каждое обращение проверяется
    через Cloud Function-авторизатор (smart-captcha-gate) и затем пересылается
    в функцию callback-request.

servers:
  - url: https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net

x-yc-apigateway:
  service_account_id: ${var.SA_CALLBACK_API}
  cors:
    origin: "*"
    methods: [POST, OPTIONS]
    allowedHeaders:
      - Content-Type
      - SmartCaptcha-Token
      - X-Captcha-Token
      - X-Correlation-Id
    credentials: true
    maxAge: 3600
  variables:
    SA_CALLBACK_API:
      default: ""
      description: "Service Account ID с правами functions.functionInvoker"
    FN_SMART_CAPTCHA_GATE:
      default: ""
      description: "Function-authorizer smart-captcha-gate"
    FN_CALLBACK_REQUEST:
      default: ""
      description: "Cloud Function callback-request"

components:
  securitySchemes:
    smartCaptchaAuth:
      type: apiKey
      in: header
      # В качестве apiKey используем X-Correlation-Id, который всегда
      # отправляется клиентом/тестом. Это гарантирует запуск авторизатора
      # на каждом запросе без 401 из-за «отсутствия ключа».
      name: X-Correlation-Id
      x-yc-apigateway-authorizer:
        type: function
        function_id: ${var.FN_SMART_CAPTCHA_GATE}
        tag: $latest
        service_account_id: ${var.SA_CALLBACK_API}

paths:
  /callback/request:
    post:
      summary: Отправить заявку на обратный звонок
      operationId: sendCallbackRequest
      tags:
        - Callback

      # Включаем авторизацию через smartCaptchaAuth, которая вызывает
      # Cloud Function smart-captcha-gate. При isAuthorized:false
      # Gateway вернёт 403 и не пойдёт в callback-request.
      security:
        - smartCaptchaAuth: []

      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                phone_number:
                  type: string
                  description: "Номер телефона лида (обязателен, если нет email)"
                email:
                  type: string
                  description: "Email лида (обязателен, если нет phone_number)"
                user_name:
                  type: string
                  description: "Имя или никнейм (опционально)"
                comment:
                  type: string
                  description: "Комментарий лида (опционально)"
              additionalProperties: false

      responses:
        "200":
          description: "Заявка принята и SMS отправлена руководителю"
        "400":
          description: "Некорректный JSON или отсутствуют обязательные поля (email/phone_number)"
        "403":
          description: "SmartCaptcha не пройдена или авторизация отклонена авторизатором"
        "500":
          description: "Ошибка отправки SMS или внутренняя ошибка сервиса"

      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_CALLBACK_REQUEST}
        tag: $latest
        service_account_id: ${var.SA_CALLBACK_API}
```

---
### Переменные среды

SA_CALLBACK_API = ajecuih6n3jdng5ld41n (указан напрямую в YAML)  
FN_SMART_CAPTCHA_GATE = d4eb2tnhvgfiarjhofi7  
FN_CALLBACK_REQUEST = d4ekm8kgr6oq7cfisc68