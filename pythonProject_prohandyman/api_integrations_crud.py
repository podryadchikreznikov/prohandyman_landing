import requests
import json
import sys
from colorama import init, Fore, Style

# Инициализируем colorama (autoreset=True сбрасывает цвет после каждого print)
init(autoreset=True)

# --- Конфигурация и константы ---
API_AUTH_URL = "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net/login"
API_INTEGRATIONS_URL = "https://d5do791qvip791842fm4.sk0vql13.apigw.yandexcloud.net/integrations"

FIRM_ID = "9a33483b-dfad-44a3-a36d-102b498ec0ef"
LOGIN_PAYLOAD = {"email": "ctac23062006@gmail.com", "password": "458854Mm"}
DEFAULT_HEADERS = {"Content-Type": "application/json"}

# Символы для статуса
TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL


def wait_for_enter(prompt_message):
    """Функция для ожидания нажатия Enter."""
    print(Style.DIM + f"\n{prompt_message}")
    input()


def run_test_step(title: str, url: str, payload: dict, headers: dict, expected_status: int):
    """Выполняет один шаг теста, выводит результат и возвращает ответ в случае успеха."""
    print(f"{Style.BRIGHT}► {title}", end=" ... ")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)

        if response.status_code == expected_status:
            print(f"{TICK} (Статус: {response.status_code})")
            return response
        else:
            print(f"{CROSS} (Ожидался статус {expected_status}, получен {response.status_code})")
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
    print("\n--- Начало комплексного тестирования Integrations API ---\n")

    # --- Шаг 1: Аутентификация ---
    login_response = run_test_step("Шаг 1: Получение JWT токена", API_AUTH_URL, LOGIN_PAYLOAD, DEFAULT_HEADERS, 200)
    if not login_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось войти в систему. Тестирование прервано.")

    jwt_token = login_response.json().get("token")
    auth_headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {jwt_token}"}

    # ===================================================================================
    # Этап 1: Создание и проверка
    # ===================================================================================
    print(Fore.CYAN + "\n--- Этап 1: Создание интеграций ---")
    upsert_payload = {
        "firm_id": FIRM_ID,
        "action": "UPSERT",
        "payload": {
            "yandex_disk": {"enabled": True, "token": "fake_token_for_yandex_disk_12345"},
            "rosstat_report": {"enabled": False, "api_key": None},
            "1c_integration": {"enabled": True, "login": "user@1c.example.com"}
        }
    }
    run_test_step("Шаг 2: Добавление/обновление набора интеграций", API_INTEGRATIONS_URL, upsert_payload, auth_headers, 200)

    get_payload = {"firm_id": FIRM_ID, "action": "GET"}
    get_response = run_test_step("Шаг 3: Получение данных об интеграциях", API_INTEGRATIONS_URL, get_payload, auth_headers, 200)

    if get_response:
        try:
            integrations = get_response.json().get('integrations', {})
            assert integrations.get('yandex_disk', {}).get('enabled') is True
            assert integrations.get('1c_integration', {}).get('login') == "user@1c.example.com"
            print(f"  {TICK} Проверка данных: полученные данные соответствуют отправленным.")
        except (AssertionError, KeyError) as e:
            print(f"  {CROSS} Проверка данных: полученные данные не соответствуют ожидаемым. Ошибка: {e}")

    wait_for_enter("Нажмите Enter для перехода к частичному удалению...")

    # ===================================================================================
    # Этап 2: Частичное удаление и проверка
    # ===================================================================================
    print(Fore.CYAN + "\n--- Этап 2: Частичное удаление ---")
    delete_one_payload = {
        "firm_id": FIRM_ID,
        "action": "DELETE",
        "integration_keys": ["rosstat_report"]
    }
    run_test_step("Шаг 4: Удаление одной интеграции ('rosstat_report')", API_INTEGRATIONS_URL, delete_one_payload, auth_headers, 200)

    get_response_after_delete = run_test_step("Шаг 5: Проверка, что интеграция 'rosstat_report' удалена", API_INTEGRATIONS_URL, get_payload, auth_headers, 200)

    if get_response_after_delete:
        try:
            integrations = get_response_after_delete.json().get('integrations', {})
            assert 'rosstat_report' not in integrations
            assert 'yandex_disk' in integrations
            print(f"  {TICK} Проверка данных: ключ 'rosstat_report' отсутствует, 'yandex_disk' на месте.")
        except (AssertionError, KeyError) as e:
            print(f"  {CROSS} Проверка данных: результат удаления некорректен. Ошибка: {e}")

    wait_for_enter("Нажмите Enter для перехода к полной очистке...")

    # ===================================================================================
    # Этап 3: Полная очистка и финальная проверка
    # ===================================================================================
    print(Fore.CYAN + "\n--- Этап 3: Полная очистка ---")
    cleanup_payload = {
        "firm_id": FIRM_ID,
        "action": "DELETE",
        "integration_keys": ["yandex_disk", "1c_integration"]
    }
    run_test_step("Шаг 6: Удаление оставшихся интеграций (очистка)", API_INTEGRATIONS_URL, cleanup_payload, auth_headers, 200)

    final_check_response = run_test_step("Шаг 7: Финальная проверка (объект интеграций должен быть пустым)", API_INTEGRATIONS_URL, get_payload, auth_headers, 200)
    if final_check_response:
        try:
            integrations = final_check_response.json().get('integrations', {})
            assert integrations == {}
            print(f"  {TICK} Проверка данных: объект интеграций успешно очищен.")
        except (AssertionError, KeyError) as e:
            print(f"  {CROSS} Проверка данных: объект интеграций не пуст. Ошибка: {e}")

    print("\n--- Тестирование Integrations API успешно завершено ---")