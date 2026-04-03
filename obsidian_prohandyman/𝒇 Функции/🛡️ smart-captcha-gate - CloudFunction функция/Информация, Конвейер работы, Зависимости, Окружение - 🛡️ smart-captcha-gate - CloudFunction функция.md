Идентификатор - d4eb2tnhvgfiarjhofi7
Имя - smart-captcha-gate
Описание - 🛡️ Функция-авторизатор для проверки токена Yandex SmartCaptcha перед вызовом целевой функции API.
Точка входа - index.handler
Таймаут - 5 сек

---
### Конвейер работы

Эта функция вызывается API Gateway как function-authorizer перед основной функцией.

На входе:
	-> `event.headers`: ищется токен капчи в заголовках `SmartCaptcha-Token` или `X-Captcha-Token`.
	-> IP клиента извлекается из `event.requestContext.identity.sourceIp` или `event.requestContext.http.sourceIp`.

Внутренняя работа:
	-> Извлечение токена только из заголовков.
	-> Вызов верификации SmartCaptcha:
		GET `https://smartcaptcha.yandexcloud.net/validate?secret=<SERVER_KEY>&token=<TOKEN>&ip=<IP>`
	-> Анализ ответа: `{ "status": "ok" }` — успех, иначе — отказ.
	-> Формирование спец-ответа для API Gateway: `{"isAuthorized": true/false, "context": {"captcha": "ok"}}`.

На выходе:
	-> `{"isAuthorized": true, "context": {"captcha": "ok"}}` — пропускает запрос к целевой функции.
	-> `{"isAuthorized": false}` — API Gateway вернет 403 Forbidden.

---
### Зависимости и окружение

- Необходимые утилиты:
	- `utils/util_log/logger.py` — JsonLogger для логирования
- Переменные окружения:
	- `SMARTCAPTCHA_SERVER_KEY` — серверный ключ SmartCaptcha (из раздела "🧩 Yandex SmartCaptcha")

Примечания:
- Токен рекомендуется передавать в заголовке `SmartCaptcha-Token`.
- IP можно опускать — SmartCaptcha валидация корректна и без него, но при наличии `sourceIp` он будет добавлен.
- Токен из body не используется.
