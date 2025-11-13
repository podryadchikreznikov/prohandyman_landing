import requests
import json
import sys
from colorama import init, Fore, Style

# Инициализируем colorama (autoreset=True сбрасывает цвет после каждого print)
init(autoreset=True)

# --- Конфигурация и константы ---
API_AUTH_URL = "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net/login"
API_MGMT_URL = "https://d5dc1h8l3tgaa483aj1g.laqt4bj7.apigw.yandexcloud.net"  # employees-and-firms-api

# Тестовый пользователь (владелец фирмы)
OWNER_LOGIN_PAYLOAD = {"email": "ctac23062006@gmail.com", "password": "458854Mm"}

# Название тестовой фирмы
TEST_FIRM_NAME = "Test Firm for Lifecycle"

DEFAULT_HEADERS = {"Content-Type": "application/json"}
TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL


def run_test_step(title: str, url: str, payload: dict, headers: dict, expected_status: int, method: str = "POST"):
    """Выполняет один шаг теста, выводит результат и возвращает ответ в случае успеха."""
    print(f"{Style.BRIGHT}► {title}", end=" ... ")

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=20)
        else:
            response = requests.post(url, json=payload, headers=headers, timeout=20)

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
    print("\n--- Начало тестирования жизненного цикла фирмы (create/get-user-data/delete) ---\n")

    # --- Шаг 1: Аутентификация владельца ---
    login_resp = run_test_step("Шаг 1: Аутентификация владельца", API_AUTH_URL, OWNER_LOGIN_PAYLOAD,
                               DEFAULT_HEADERS, 200)
    if not login_resp:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось войти в систему. Тестирование прервано.")

    owner_token = login_resp.json().get("token")
    auth_headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {owner_token}"}

    # --- Шаг 2: Получение данных пользователя ДО создания фирмы ---
    get_user_data_resp_before = run_test_step("Шаг 2: Получение данных пользователя (до создания фирмы)",
                                              f"{API_MGMT_URL}/get-user-data",
                                              {}, auth_headers, 200, method="GET")
    if get_user_data_resp_before:
        user_data_before = get_user_data_resp_before.json()
        print(Fore.CYAN + f"  Фирм до создания: {len(user_data_before.get('firms', []))}")

    # --- Шаг 3: Создание новой фирмы ---
    create_firm_payload = {"firm_name": TEST_FIRM_NAME}
    create_firm_resp = run_test_step("Шаг 3: Создание новой фирмы",
                                     f"{API_MGMT_URL}/firms/create",
                                     create_firm_payload, auth_headers, 201)
    if not create_firm_resp:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось создать фирму. Тестирование прервано.")

    firm_id = create_firm_resp.json().get("firm_id")
    print(Fore.CYAN + f"  Создана фирма с ID: {firm_id}")

    # --- Шаг 4: Получение данных пользователя ПОСЛЕ создания фирмы ---
    get_user_data_resp_after = run_test_step("Шаг 4: Получение данных пользователя (после создания фирмы)",
                                             f"{API_MGMT_URL}/get-user-data",
                                             {}, auth_headers, 200, method="GET")
    if get_user_data_resp_after:
        user_data_after = get_user_data_resp_after.json()
        firms_after = user_data_after.get('firms', [])
        print(Fore.CYAN + f"  Фирм после создания: {len(firms_after)}")
        
        # Проверка, что новая фирма присутствует
        firm_found = any(f.get('firm_id') == firm_id for f in firms_after)
        if firm_found:
            print(Fore.GREEN + f"  {TICK} Новая фирма найдена в данных пользователя")
        else:
            print(Fore.RED + f"  {CROSS} Новая фирма НЕ найдена в данных пользователя")

    # --- Шаг 5: Попытка создать вторую фирму (должна вернуть 409) ---
    run_test_step("Шаг 5: Попытка создать вторую фирму (ожидается 409 Conflict)",
                  f"{API_MGMT_URL}/firms/create",
                  {"firm_name": "Second Firm Attempt"}, auth_headers, 409)

    # --- Шаг 6: Удаление фирмы ---
    delete_firm_resp = run_test_step("Шаг 6: Удаление фирмы",
                                     f"{API_MGMT_URL}/firms/{firm_id}/delete",
                                     {}, auth_headers, 200)
    if not delete_firm_resp:
        print(Fore.YELLOW + f"\n⚠ Предупреждение: не удалось удалить фирму {firm_id}. Возможно, потребуется ручная очистка.")
    else:
        print(Fore.GREEN + f"  Фирма {firm_id} успешно удалена")

    # --- Шаг 7: Получение данных пользователя ПОСЛЕ удаления фирмы ---
    get_user_data_resp_final = run_test_step("Шаг 7: Получение данных пользователя (после удаления фирмы)",
                                             f"{API_MGMT_URL}/get-user-data",
                                             {}, auth_headers, 200, method="GET")
    if get_user_data_resp_final:
        user_data_final = get_user_data_resp_final.json()
        firms_final = user_data_final.get('firms', [])
        print(Fore.CYAN + f"  Фирм после удаления: {len(firms_final)}")
        
        # Проверка, что фирма удалена
        firm_still_exists = any(f.get('firm_id') == firm_id for f in firms_final)
        if not firm_still_exists:
            print(Fore.GREEN + f"  {TICK} Фирма успешно удалена из данных пользователя")
        else:
            print(Fore.RED + f"  {CROSS} Фирма всё ещё присутствует в данных пользователя")

    print("\n--- Тестирование жизненного цикла фирмы успешно завершено ---")
