
Идентификатор - d5dppitf9vbj18mkmls1
Имя - auth-api
Служебный домен - https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net

---
### Спецификация

```yaml
openapi: "3.0.0"
info:
  title: auth-api
  version: "1.2.1"

x-yc-apigateway:
  service_account_id: ${var.SA_AUTH_API}
  cors:
    origin: "*"
    methods: [POST, OPTIONS]
    allowedHeaders: ["Content-Type", "Authorization"]
    credentials: true
    maxAge: 3600
  variables:
    SA_AUTH_API:
      default: ""
      description: "Service Account ID with functions.functionInvoker"
    FN_REGISTER_REQUEST:
      default: ""
      description: "Cloud Function: request registration code"
    FN_REGISTER_CONFIRM:
      default: ""
      description: "Cloud Function: confirm registration"
    FN_ACCEPT_INVITATION:
      default: ""
      description: "Cloud Function: accept invitation"
    FN_LOGIN:
      default: ""
      description: "Cloud Function: login"
    FN_REFRESH_TOKEN:
      default: ""
      description: "Cloud Function: refresh token"
    FN_PASSWORD_MANAGER:
      default: ""
      description: "Cloud Function: password manager"
    FUNCTION_TAG:
      default: "$latest"
      description: "Function version tag"

paths:
  /register-request:
    post:
      summary: Request registration code
      operationId: registerRequest
      tags: [Authentication]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string, description: "Email пользователя (обязателен если нет phone_number)" }
                phone_number: { type: string, description: "Номер телефона (обязателен если нет email)" }
                password: { type: string, description: "Пароль пользователя" }
                user_name: { type: string, description: "Имя пользователя" }
                verification_method: { type: string, enum: [email, sms], description: "Канал отправки кода: email или sms" }
              required: [password, user_name]
      responses:
        "200":
          description: Registration code has been issued (or email sent).
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_REGISTER_REQUEST}
        tag: ${var.FUNCTION_TAG}

  /register-confirm:
    post:
      summary: Confirm registration
      operationId: registerConfirm
      tags: [Authentication]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string, description: "Email пользователя (обязателен если нет phone_number)" }
                phone_number: { type: string, description: "Номер телефона (обязателен если нет email)" }
                code: { type: string, description: "Код подтверждения" }
              required: [code]
      responses:
        "200":
          description: Registration successfully confirmed.
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_REGISTER_CONFIRM}
        tag: ${var.FUNCTION_TAG}

  /accept-invitation:
    post:
      summary: Accept invitation
      operationId: acceptInvitation
      tags: [Authentication]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                invitation_key: { type: string }
              required: [invitation_key]
      responses:
        "200":
          description: Invitation accepted successfully.
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_ACCEPT_INVITATION}
        tag: ${var.FUNCTION_TAG}

  /login:
    post:
      summary: Login
      operationId: login
      tags: [Authentication]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string, description: "Email пользователя (обязателен если нет phone_number)" }
                phone_number: { type: string, description: "Номер телефона (обязателен если нет email)" }
                password: { type: string, description: "Пароль пользователя" }
              required: [password]
      responses:
        "200":
          description: Login successful; tokens returned.
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_LOGIN}
        tag: ${var.FUNCTION_TAG}

  /refresh-token:
    post:
      summary: Refresh token
      operationId: refreshToken
      tags: [Authentication]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string }
                password: { type: string }
              required: [email, password]
      responses:
        "200":
          description: Token successfully refreshed.
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_REFRESH_TOKEN}
        tag: ${var.FUNCTION_TAG}

  /password/request-reset:
    post:
      summary: Request password reset
      operationId: requestPasswordReset
      tags: [Password Management]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string }
              required: [email]
      responses:
        "200":
          description: Password reset code has been sent.
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_PASSWORD_MANAGER}
        tag: ${var.FUNCTION_TAG}
        context:
          action: "REQUEST_RESET"

  /password/reset:
    post:
      summary: Reset password
      operationId: resetPassword
      tags: [Password Management]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                email: { type: string }
                new_password: { type: string }
                current_password_hash: { type: string }
              required: [email, new_password, current_password_hash]
      responses:
        "200":
          description: Password has been reset successfully.
      x-yc-apigateway-integration:
        type: cloud_functions
        function_id: ${var.FN_PASSWORD_MANAGER}
        tag: ${var.FUNCTION_TAG}
        context:
          action: "RESET"

```

---
### Переменные среды

SA_AUTH_API = aje4dvfc3964dgg1d74t
FN_REGISTER_REQUEST = d4ed1sm14vdat7spiqa2
FN_REGISTER_CONFIRM = d4e7ojdqgpcirm5mjmca
FN_ACCEPT_INVITATION = d4e9fp93mis8tuds725n
FN_LOGIN = d4ebfaik113n6nna6mut
FN_REFRESH_TOKEN = d4e71eji4nfvf9mi4p09
FN_PASSWORD_MANAGER = d4e32tlus7fal6gs96iv 