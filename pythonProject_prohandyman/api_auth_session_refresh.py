# test_auth_session_refresh.py
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
login_payload = {
    "email": "ctacnazarov23@gmail.com",
    "password": "458854Mm"
}
incorrect_refresh_payload = {
    "email": "ctacnazarov23@gmail.com",
    "password": "WrongPassword123"
}

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
    print("\n--- Начало тестирования очистки сессий и обновления токенов ---\n")

    # Шаг 1: Первоначальная авторизация
    login_response_1 = run_test_step(
        "Шаг 1: Первоначальная авторизация",
        f"{BASE_URL}/login",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    if not login_response_1:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось войти в систему. Тестирование прервано.")

    initial_token = login_response_1.json().get("token")
    print(Fore.CYAN + f"  ℹ Получен начальный токен: ...{initial_token[-20:] if initial_token else 'N/A'}")

    # Шаг 2: Принудительное обновление токена (refresh)
    refresh_response = run_test_step(
        "Шаг 2: Принудительное обновление токена",
        f"{BASE_URL}/refresh-token",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    if not refresh_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось обновить токен. Тестирование прервано.")

    refreshed_token = refresh_response.json().get("token")
    print(Fore.CYAN + f"  ℹ Получен обновлённый токен: ...{refreshed_token[-20:] if refreshed_token else 'N/A'}")

    # Шаг 3: Проверка обновления с неверными данными (ожидается отказ)
    run_test_step(
        "Шаг 3: Попытка обновления с неверным паролем (ожидается отказ)",
        f"{BASE_URL}/refresh-token",
        incorrect_refresh_payload,
        DEFAULT_HEADERS,
        expected_statuses=[401]
    )

    # Шаг 4: Повторная авторизация после обновления
    login_response_2 = run_test_step(
        "Шаг 4: Повторная авторизация после обновления",
        f"{BASE_URL}/login",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    if not login_response_2:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось выполнить повторный вход. Тестирование прервано.")

    new_login_token = login_response_2.json().get("token")
    print(Fore.CYAN + f"  ℹ Получен токен после повторного входа: ...{new_login_token[-20:] if new_login_token else 'N/A'}")

    # Шаг 5: Финальная проверка согласованности токенов
    print(f"\n{Style.BRIGHT}► Шаг 5: Финальная проверка согласованности токенов")
    
    print(f"  {Style.BRIGHT}Сравнение: начальный токен vs обновлённый токен", end=" ... ")
    if initial_token and refreshed_token:
        if initial_token != refreshed_token:
            print(f"{TICK} (Токены различаются - обновление работает)")
        else:
            print(f"{CROSS} (Токены идентичны - обновление не произошло)")
    else:
        print(f"{CROSS} (Один из токенов отсутствует)")

    print(f"  {Style.BRIGHT}Сравнение: обновлённый токен vs токен после повторного входа", end=" ... ")
    if refreshed_token and new_login_token:
        if refreshed_token == new_login_token:
            print(f"{TICK} (Токены совпадают - сессия синхронизирована)")
        else:
            print(f"{CROSS} (Токены различаются)")
            print(Fore.YELLOW + "    ⚠ Это может быть нормально, если токены обновляются при каждом входе")
    else:
        print(f"{CROSS} (Один из токенов отсутствует)")

    # Шаг 6: Второе обновление токена (проверка ротации)
    refresh_response_2 = run_test_step(
        "Шаг 6: Второе обновление токена",
        f"{BASE_URL}/refresh-token",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    second_refreshed = refresh_response_2.json().get("token") if refresh_response_2 else None
    print(f"  {Style.BRIGHT}Проверка: второй refresh выдаёт новый токен", end=" ... ")
    if second_refreshed and second_refreshed != new_login_token:
        print(f"{TICK}")
    else:
        print(f"{CROSS}")

    # Шаг 7: Повторный вход должен вернуть последний токен
    login_response_3 = run_test_step(
        "Шаг 7: Повторный вход после второго refresh",
        f"{BASE_URL}/login",
        login_payload,
        DEFAULT_HEADERS,
        expected_statuses=[200]
    )
    final_login_token = login_response_3.json().get("token") if login_response_3 else None
    print(f"  {Style.BRIGHT}Проверка: login возвращает последний токен", end=" ... ")
    if final_login_token and second_refreshed and final_login_token == second_refreshed:
        print(f"{TICK}")
    else:
        print(f"{CROSS}")

    print("\n--- Тестирование очистки сессий и обновления токенов успешно завершено ---")
