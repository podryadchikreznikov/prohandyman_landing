# test_auth_registration.py
import requests
import json
import sys
from colorama import init, Fore, Style

# Инициализируем colorama (autoreset=True сбрасывает цвет после каждого print)
init(autoreset=True)

# --- Конфигурация и константы ---
BASE_URL = "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net"
DEFAULT_HEADERS = {"Content-Type": "application/json"}

# --- Данные для теста ---
DEFAULT_EMAIL = "ctacnazarov23@gmail.com"
DEFAULT_PHONE_NUMBER = "79097033965"
DEFAULT_PASSWORD = "458854Mm"
DEFAULT_USER_NAME = "Nazarov"


# --- Вспомогательные функции ---
def choose_delivery_channel() -> str:
    print(Fore.YELLOW + "  Выберите способ отправки кода подтверждения:")
    print(Fore.YELLOW + "    0 — Email")
    print(Fore.YELLOW + "    1 — SMS (телефон)")
    while True:
        choice = input("Способ (0/1, по умолчанию 0): ").strip() or "0"
        if choice in {"0", "1"}:
            return "email" if choice == "0" else "sms"
        print(Fore.RED + "  Неверный выбор. Введите 0 или 1.")


def build_register_payload(channel: str) -> dict:
    payload = {
        "password": DEFAULT_PASSWORD,
        "user_name": DEFAULT_USER_NAME,
    }
    if DEFAULT_EMAIL:
        payload["email"] = DEFAULT_EMAIL
    if DEFAULT_PHONE_NUMBER:
        payload["phone_number"] = DEFAULT_PHONE_NUMBER

    payload["verification_method"] = "email" if channel == "email" else "sms"
    return payload

# Символы для статуса
TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL


def run_test_step(title: str, url: str, payload: dict, headers: dict, expected_statuses: list):
    """Выполняет один шаг теста, выводит результат и возвращает ответ в случае успеха."""
    print(f"{Style.BRIGHT}► {title}", end=" ... ")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code in expected_statuses:
            print(f"{TICK} (Статус: {response.status_code})")
            return response
        else:
            print(f"{CROSS} (Ожидался статус в {expected_statuses}, получен {response.status_code})")
            print(Fore.RED + "  Текст ошибки:")
            try:
                error_json = response.json()
                print(Fore.RED + json.dumps(error_json, indent=4, ensure_ascii=False))
            except json.JSONDecodeError:
                print(Fore.RED + response.text)
            return None

    except requests.exceptions.RequestException as e:
        print(f"{CROSS} (Исключение во время запроса)")
        print(Fore.RED + f"  Текст ошибки: {e}")
        return None


if __name__ == "__main__":
    print("\n--- Начало тестирования регистрации пользователя ---\n")

    channel = choose_delivery_channel()
    register_payload = build_register_payload(channel)
    identifier_value = register_payload.get("email") or register_payload.get("phone_number")
    channel_label = "Email" if channel == "email" else "SMS (телефон)"

    print(Fore.CYAN + f"\n  ℹ Выбран канал: {channel_label}")
    if channel == "email":
        print(Fore.CYAN + f"    Email: {register_payload['email']}")
    else:
        print(Fore.CYAN + f"    Телефон: {register_payload['phone_number']}")

    # Шаг 1: Запрос на регистрацию
    # Считаем успешным, если код отправлен (200) или пользователь уже существует (409)
    register_response = run_test_step(
        "Шаг 1: Запрос на регистрацию (отправка кода подтверждения)",
        f"{BASE_URL}/register-request",
        register_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200, 201, 409]
    )

    if not register_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось выполнить запрос на регистрацию. Тестирование прервано.")

    # Анализ результата
    status_code = register_response.status_code
    if status_code == 200:
        if channel == "email":
            print(Fore.CYAN + "\n  ℹ Код подтверждения отправлен на email.")
            print(Fore.CYAN + f"    Email: {identifier_value}")
        else:
            print(Fore.CYAN + "\n  ℹ Код подтверждения отправлен по SMS на телефон.")
            print(Fore.CYAN + f"    Телефон: {identifier_value}")
        print(Fore.CYAN + "  ℹ Для завершения регистрации необходимо:")
        print(Fore.CYAN + "    1. Проверить email и получить код подтверждения")
        print(Fore.CYAN + "    2. Вызвать эндпоинт /register-confirm с кодом")
        print(Fore.YELLOW + "\n  ⚠ Примечание: Автоматическое подтверждение не реализовано в этом тесте.")
    elif status_code == 201:
        try:
            body = register_response.json()
            token = body.get("token")
        except json.JSONDecodeError:
            token = None
        print(Fore.CYAN + "\n  ℹ Пользователь автоматически подтверждён (AUTO_CONFIRM_MODE).")
        if token:
            print(Fore.GREEN + "  ✓ Получен token:")
            print(Fore.GREEN + f"  {token}")
        else:
            print(Fore.YELLOW + "  ⚠ Ответ 201 без JSON-тела/токена.")
        print(Fore.CYAN + "  ℹ Можно продолжить с тестом авторизации (api_auth_login_and_user_data.py)")
    elif status_code == 409:
        if channel == "email":
            print(Fore.YELLOW + "\n  ⚠ Пользователь с таким email уже зарегистрирован.")
        else:
            print(Fore.YELLOW + "\n  ⚠ Пользователь с таким номером телефона уже зарегистрирован.")
        print(Fore.CYAN + "  ℹ Можно продолжить с тестом авторизации (api_auth_login_and_user_data.py)")

    print("\n--- Тестирование регистрации завершено ---")
