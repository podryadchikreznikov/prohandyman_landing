```python
# password_manager_email.py
# Локальный модуль для отправки email, специфичный для функции password-manager.

import os
import requests
from utils import JsonLogger

def _send_email(recipient_email: str, subject: str, html_body: str) -> bool:
    """
    Приватная функция для отправки email через API Unisender.
    Использует переменные окружения для конфигурации.
    """
    logger = JsonLogger()
    api_key = os.environ.get('UNISENDER_API_KEY')
    sender_email = os.environ.get('UNISENDER_SENDER_EMAIL')
    sender_name = os.environ.get('UNISENDER_SENDER_NAME')
    list_id = os.environ.get('UNISENDER_LIST_ID')

    if not all([api_key, sender_email, sender_name, list_id]):
        logger.error("unisender.config_incomplete")
        return False

    api_url = 'https://api.unisender.com/ru/api/sendEmail'
    params = {
        'api_key': api_key, 'format': 'json', 'email': recipient_email,
        'sender_name': sender_name, 'sender_email': sender_email,
        'subject': subject, 'body': html_body, 'list_id': list_id,
    }

    try:
        logger.info("unisender.send_email", recipient=recipient_email, subject=subject)
        response = requests.post(api_url, data=params, timeout=10)
        response.raise_for_status()

        response_data = response.json()
        if response_data.get('error'):
            logger.error("unisender.error", error=response_data.get('error'))
            return False

        logger.info("unisender.sent_ok", response=response_data)
        return True

    except requests.exceptions.RequestException as e:
        logger.error("unisender.request_exception", error=str(e))
        return False
    except Exception as e:
        logger.error("unisender.unexpected_error", error=str(e))
        return False

def send_password_reset_hash(recipient_email: str, password_hash: str) -> bool:
    """Формирует и отправляет email с хешем для сброса пароля."""

    email_subject = 'Запрос на сброс пароля'
    html_body = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f4f4f4; }}
            .container {{ background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; }}
            .hash-box {{ font-family: 'Courier New', monospace; font-size: 14px; word-break: break-all; margin: 20px 0; padding: 15px; background-color: #eef1f3; border-radius: 5px; text-align: left; }}
            p {{ color: #555; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Сброс пароля</h2>
            <p>Здравствуйте!</p>
            <p>Вы запросили сброс пароля для вашего аккаунта. Чтобы продолжить, скопируйте следующий ключ подтверждения и вставьте его на странице сброса пароля вместе с вашим новым паролем.</p>
            <div class="hash-box">{password_hash}</div>
            <p><b>Этот ключ является вашим текущим зашифрованным паролем и необходим для подтверждения операции.</b></p>
            <p>Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.</p>
        </div>
    </body>
    </html>
    """
    return _send_email(recipient_email, email_subject, html_body)