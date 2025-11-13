
Имя - balansoved-web-notifications

Тип - Push-уведомления в браузере (Web Push)

Идентификатор (ARN) - arn:aws:sns::b1g2bgg0i9r8beucbthc:app/WEB/balansoved-web-notifications
Публичный VAPID-ключ - BCyZSlvKpYoRx_SaFpHtqyryq9lmutEyJ-hpeh_1jEcwTPvcJRtpv0VGw_zfOSZVjIzLCj5ggWgIyfWJQJSClZI

---
#### Далее примеры из документации
#### Пример создания эндпоинта для устройства

```python
try:
    response = client.create_platform_endpoint(
        PlatformApplicationArn="<ARN_приложения>",
        Token="<push_токен>",
    )
    print(f'Endpoint ARN: {response["EndpointArn"]}')

except botocore.exceptions.ClientError as error:
    print(f"Error: {error}")
```

#### Пример отправки сообщения в эндпоинт

```python
try:
    response = client.publish(
        TargetArn="<ARN_эндпоинта>",
        Message=json.dumps({
            "default": "<текст_уведомления>",
            "WEB": "<текст_уведомления>",
        }),
        MessageStructure="json",
    )
    print(f'Message ID: {response["MessageId"]}')

except botocore.exceptions.ClientError as error:
    print(f"Error: {error}")
```