# notification_system_test.py
#
# Этот скрипт выполняет полный цикл тестирования системы уведомлений.
# 1. Сначала вызывается функция логинизации для получения JWT токена.
# 2. Этот токен используется во всех последующих запросах к защищенным эндпоинтам API в заголовке Authorization: Bearer <token>.
# 3. Сценарий имитирует создание подписки, отправку и управление уведомлением, а затем очистку тестовых данных.

import requests
import json
import uuid
import jwt
import time
from urllib.parse import quote

# --- КОНФИГУРАЦИЯ ---
AUTH_API_URL = "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net"
NOTIFICATIONS_API_URL = "https://d5dqe519ci8oku6g0075.bixf7e87.apigw.yandexcloud.net"
TEST_EMAIL = "ctac23062006@gmail.com"
TEST_PASSWORD = "458854Mm"

# --- ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ДЛЯ ХРАНЕНИЯ СОСТОЯНИЯ ---
jwt_token = None
user_id = None
endpoint_arn = None
notice_id = None


# --- УТИЛИТЫ ---

def log_request(method, url, data=None):
    """Логирует исходящий запрос в лаконичном виде."""
    print(f"\n---> {method} {url}")
    if data:
        print(f"     BODY: {json.dumps(data)}")


def log_response(response):
    """Логирует ответ от сервера и возвращает JSON."""
    print(f"<--- {response.status_code} {response.reason}")
    try:
        response_json = response.json()
        print(f"     DATA: {json.dumps(response_json, indent=2)}")
        return response_json
    except json.JSONDecodeError:
        print(f"     BODY: {response.text}")
        return None


def get_auth_headers():
    """Возвращает стандартный заголовок авторизации."""
    if not jwt_token:
        raise ValueError("Ошибка: JWT токен не получен.")
    return {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json"
    }


# --- ШАГИ ТЕСТОВОГО СЦЕНАРИЯ ---

def step_1_login():
    """Шаг 1: Авторизация и получение JWT."""
    global jwt_token, user_id
    print("\n--- [ШАГ 1] Авторизация пользователя ---")
    url = f"{AUTH_API_URL}/login"
    payload = {"email": TEST_EMAIL, "password": TEST_PASSWORD}

    log_request("POST", url, data=payload)
    response = requests.post(url, json=payload)
    response_data = log_response(response)

    response.raise_for_status()
    jwt_token = response_data.get("token")

    # ИСПРАВЛЕНО: Декодируем токен БЕЗ ПРОВЕРКИ ПОДПИСИ, чтобы просто извлечь payload.
    # Это необходимо, т.к. у нас нет серверного JWT_SECRET.
    decoded_payload = jwt.decode(jwt_token, options={"verify_signature": False})
    user_id = decoded_payload.get("user_id")
    print(f"Успешно авторизован. User ID извлечен из токена: {user_id}")


def step_2_create_subscription():
    """Шаг 2: Создание эндпоинта (подписки на уведомления)."""
    global endpoint_arn
    print("\n--- [ШАГ 2] Создание эндпоинта ---")
    url = f"{NOTIFICATIONS_API_URL}/subscriptions"
    fake_push_token = f"fake-test-token-{uuid.uuid4()}"
    payload = {
        "push_token": fake_push_token,
        "device_info": {"user_agent": "Python Test Script"}
    }

    log_request("POST", url, data=payload)
    response = requests.post(url, headers=get_auth_headers(), json=payload)
    response_data = log_response(response)

    response.raise_for_status()
    endpoint_arn = response_data.get("endpoint_arn")
    print(f"Успешно создан эндпоинт. ARN: {endpoint_arn}")


def step_3_send_notification():
    """Шаг 3: Отправка тестового уведомления."""
    print("\n--- [ШАГ 3] Инициирование отправки уведомления ---")
    url = f"{NOTIFICATIONS_API_URL}/send-notification"
    payload = {
        "user_id_to_notify": user_id,
        "payload": {
            "title": "Тестовое уведомление",
            "body": f"Сообщение отправлено в {time.strftime('%H:%M:%S')}"
        }
    }

    log_request("POST", url, data=payload)
    response = requests.post(url, headers=get_auth_headers(), json=payload)
    log_response(response)
    response.raise_for_status()
    print("Запрос на отправку успешно выполнен. Ожидание 2 сек...")
    time.sleep(2)


def step_4_check_new_notices():
    """Шаг 4: Проверка появления нового уведомления в списке."""
    global notice_id
    print("\n--- [ШАГ 4] Проверка списка новых уведомлений ---")
    url = f"{NOTIFICATIONS_API_URL}/notices"

    log_request("GET", url)
    response = requests.get(url, headers=get_auth_headers())
    response_data = log_response(response)

    response.raise_for_status()
    notices = response_data.get("data", [])
    if not notices:
        raise ValueError("Список новых уведомлений пуст.")

    latest_notice = notices[0]
    notice_id = latest_notice.get("notice_id")
    print(f"Проверка успешна: найдено новое уведомление с ID: {notice_id}")


def step_5_mark_as_delivered_and_archive():
    """Шаг 5: Пометка как доставленного и архивация."""
    print("\n--- [ШАГ 5.1] Пометка уведомления как доставленного ---")
    url_mark = f"{NOTIFICATIONS_API_URL}/notices/mark-as-delivered"
    payload_mark = {"notice_ids": [notice_id]}

    log_request("POST", url_mark, data=payload_mark)
    response_mark = requests.post(url_mark, headers=get_auth_headers(), json=payload_mark)
    log_response(response_mark)
    response_mark.raise_for_status()

    print("\n--- [ШАГ 5.2] Архивация уведомления ---")
    url_archive = f"{NOTIFICATIONS_API_URL}/notices/archive"
    payload_archive = {"notice_id": notice_id}

    log_request("POST", url_archive, data=payload_archive)
    response_archive = requests.post(url_archive, headers=get_auth_headers(), json=payload_archive)
    log_response(response_archive)
    response_archive.raise_for_status()
    print("Уведомление успешно обработано и заархивировано.")


def step_6_delete_subscription():
    """Шаг 6: Удаление созданной подписки для очистки."""
    print("\n--- [ШАГ 6] Удаление эндпоинта для очистки ---")
    encoded_arn = quote(endpoint_arn, safe='')
    url = f"{NOTIFICATIONS_API_URL}/subscriptions/{encoded_arn}"

    log_request("DELETE", url)
    response = requests.delete(url, headers=get_auth_headers())
    log_response(response)
    response.raise_for_status()
    print("Эндпоинт успешно удален.")


if __name__ == "__main__":
    try:
        step_1_login()
        step_2_create_subscription()
        step_3_send_notification()
        step_4_check_new_notices()
        step_5_mark_as_delivered_and_archive()
        step_6_delete_subscription()
        print("\n✅✅✅ Все шаги тестирования системы уведомлений успешно завершены! ✅✅✅")
    except requests.exceptions.HTTPError as e:
        print(f"\n❌❌❌ КРИТИЧЕСКАЯ ОШИБКА: HTTP-запрос провалился! ❌❌❌")
        print(f"URL: {e.request.url}")
        print(f"Статус-код: {e.response.status_code}")
        print(f"Ответ: {e.response.text}")
    except Exception as e:
        print(f"\n❌❌❌ КРИТИЧЕСКАЯ ОШИБКА: {e} ❌❌❌")