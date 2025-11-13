# test_auth_login_and_user_data.py
import os
import requests
import json
import sys
import jwt
from colorama import init, Fore, Style

init(autoreset=True)

# --- Конфигурация и константы ---
AUTH_API_URL = os.getenv("AUTH_API_URL", "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net")
MGMT_API_URL = os.getenv("MGMT_API_URL", "https://d5dc1h8l3tgaa483aj1g.g3ab4gln.apigw.yandexcloud.net")
DEFAULT_HEADERS = {"Content-Type": "application/json"}

# --- Данные для теста ---
DEFAULT_EMAIL = "ctacnazarov23@gmail.com"
DEFAULT_PHONE_NUMBER = "79097033965"
DEFAULT_PASSWORD = "458854Mm"

login_payload = {
    "email": DEFAULT_EMAIL,
    "password": DEFAULT_PASSWORD,
}

login_phone_payload = {
    "phone_number": DEFAULT_PHONE_NUMBER,
    "password": DEFAULT_PASSWORD,
}

incorrect_login_payload = {
    "email": DEFAULT_EMAIL,
    "password": "WrongPassword123"
}

TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL


def run_test_step(title: str, url: str, payload: dict, headers: dict, expected_statuses: list, method: str = "POST"):
    print(f"{Style.BRIGHT}► {title}", end=" ... ")
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=15)
        else:
            response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code in expected_statuses:
            print(f"{TICK} (Статус: {response.status_code})")
            return response
        else:
            print(f"{CROSS} (Ожидался статус в {expected_statuses}, получен {response.status_code})")
            print(Fore.RED + "  Текст ошибки:")
            try:
                print(Fore.RED + json.dumps(response.json(), indent=4, ensure_ascii=False))
            except json.JSONDecodeError:
                print(Fore.RED + response.text)
            return None
    except requests.exceptions.RequestException as e:
        print(f"{CROSS} (Исключение во время запроса)")
        print(Fore.RED + f"  Текст ошибки: {e}")
        return None


if __name__ == "__main__":
    print("\n--- Начало тестирования авторизации и получения данных пользователя ---\n")
    print(Fore.YELLOW + f"  ℹ AUTH_API_URL = {AUTH_API_URL}")
    print(Fore.YELLOW + f"  ℹ MGMT_API_URL = {MGMT_API_URL}\n")

    # Шаг 1: Первоначальная авторизация (email + пароль)
    login_response = run_test_step(
        "Шаг 1: Первоначальная авторизация (email)",
        f"{AUTH_API_URL}/login",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    if not login_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось войти в систему. Тестирование прервано.")

    token = login_response.json().get("token")
    print(Fore.CYAN + f"  ℹ Получен JWT токен: ...{token[-20:] if token else 'N/A'}")

    # Шаг 2: Авторизация по номеру телефона
    login_phone_response = run_test_step(
        "Шаг 2: Авторизация по номеру телефона",
        f"{AUTH_API_URL}/login",
        login_phone_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )

    if login_phone_response:
        token_phone = login_phone_response.json().get("token")
        print(Fore.CYAN + f"  ℹ Получен JWT токен (телефон): ...{token_phone[-20:] if token_phone else 'N/A'}")

    # Шаг 3: Проверка входа с неверным паролем
    run_test_step(
        "Шаг 3: Проверка входа с неверным паролем (ожидается отказ)",
        f"{AUTH_API_URL}/login",
        incorrect_login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[401]
    )

    # Шаг 4: Получение данных пользователя (используем user_id из токена)
    try:
        # Извлекаем user_id из токена для теста
        decoded = jwt.decode(token, options={"verify_signature": False})
        user_id = decoded.get("sub") or decoded.get("user_id")
    except Exception:
        user_id = None
    
    if not user_id:
        print(f"{CROSS} Не удалось извлечь user_id из токена")
        sys.exit(1)
    
    # Запрос с user_id (без авторизации)
    user_data_response = run_test_step(
        "Шаг 3: Получение данных пользователя",
        f"{MGMT_API_URL}/get-user-data?user_id={user_id}",
        {},
        DEFAULT_HEADERS,
        expected_statuses=[200],
        method="GET"
    )

    if user_data_response:
        user_data = user_data_response.json()
        print(Fore.CYAN + f"\n  ℹ Данные пользователя:")
        print(Fore.CYAN + f"    - User ID: {user_data.get('user_id', 'N/A')}")
        print(Fore.CYAN + f"    - Email: {user_data.get('email', 'N/A')}")
        print(Fore.CYAN + f"    - User Name: {user_data.get('user_name', 'N/A')}")
        firms = user_data.get('firms', [])
        print(Fore.CYAN + f"    - Количество фирм: {len(firms)}")
        if firms:
            for i, firm in enumerate(firms, 1):
                print(Fore.CYAN + f"      {i}. {firm.get('firm_name', 'N/A')} (ID: {firm.get('firm_id', 'N/A')})")
    else:
        print(Fore.YELLOW + "\n  ⚠ Эндпойнт /get-user-data не найден на MGMT_API_URL. Проверь MGMT_API_URL (переменная окружения) и укажи шлюз employees-and-firms.")

    # Шаг 5: Повторная авторизация для проверки стабильности токена
    login_response_2 = run_test_step(
        "Шаг 5: Повторная авторизация (проверка стабильности)",
        f"{AUTH_API_URL}/login",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    if login_response_2:
        new_token = login_response_2.json().get("token")
        print(f"\n{Style.BRIGHT}► Шаг 6: Сравнение токенов", end=" ... ")
        if token and new_token and token == new_token:
            print(f"{TICK} (Токены идентичны)")
        else:
            print(f"{CROSS} (Токены различаются)")
            print(Fore.YELLOW + "  ⚠ Это нормально, если токены обновляются при каждом входе")

    print("\n--- Тестирование авторизации и получения данных пользователя успешно завершено ---")
