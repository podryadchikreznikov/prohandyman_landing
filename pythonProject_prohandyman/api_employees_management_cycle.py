import requests
import json
import sys
from colorama import init, Fore, Style

# Инициализируем colorama (autoreset=True сбрасывает цвет после каждого print)
init(autoreset=True)

# --- Конфигурация и константы ---
API_AUTH_URL = "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net/login"
API_MGMT_URL = "https://d5dc1h8l3tgaa483aj1g.laqt4bj7.apigw.yandexcloud.net"  # employees-and-firms-api

# Администратор/Владелец, выполняющий все действия
ADMIN_LOGIN_PAYLOAD = {"email": "ctac23062006@gmail.com", "password": "458854Mm"}

# Сотрудник, над которым проводятся операции
TARGET_EMPLOYEE_EMAIL = "slavamorozov20052305@gmail.com"

# Фирма, в которой происходят все действия
FIRM_ID = "9a33483b-dfad-44a3-a36d-102b498ec0ef"

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
    print("\n--- Начало тестирования API управления фирмой и сотрудниками ---\n")

    # --- Шаг 1: Аутентификация Администратора ---
    login_resp = run_test_step("Шаг 1: Аутентификация Администратора", API_AUTH_URL, ADMIN_LOGIN_PAYLOAD,
                               DEFAULT_HEADERS, 200)
    if not login_resp: sys.exit(f"\n{CROSS} Критическая ошибка: не удалось войти в систему. Тестирование прервано.")

    admin_token = login_resp.json().get("token")
    auth_headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {admin_token}"}

    # --- Шаг 2: Добавление сотрудника в фирму ---
    create_emp_payload = {"firm_id": FIRM_ID, "email": TARGET_EMPLOYEE_EMAIL}
    create_employee_resp = run_test_step("Шаг 2: Добавление сотрудника в фирму", f"{API_MGMT_URL}/employees/create",
                                         create_emp_payload, auth_headers, 201)
    if not create_employee_resp:
        sys.exit(
            f"\n{CROSS} Критическая ошибка: не удалось добавить сотрудника. Возможно, он уже в фирме. Тестирование прервано.")
    employee_id = create_employee_resp.json().get("user_id")

    # --- Шаг 3: Получение информации о конкретном сотруднике ---
    run_test_step("Шаг 3: Получение информации о добавленном сотруднике", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees?user_id_to_get={employee_id}",
                  {}, auth_headers, 200, method="GET")

    # --- Шаг 4: Полный цикл редактирования ролей ---
    promote_payload = {"user_id_to_edit": employee_id, "sub_action": "ADD_ROLE", "role": "ADMIN"}
    run_test_step("Шаг 4.1: Повышение сотрудника до Администратора", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees/edit", promote_payload, auth_headers, 200)

    run_test_step("Шаг 4.2: Проверка нового статуса (роль ADMIN)", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees?user_id_to_get={employee_id}",
                  {}, auth_headers, 200, method="GET")

    demote_payload = {"user_id_to_edit": employee_id, "sub_action": "REMOVE_ROLE", "role": "ADMIN"}
    run_test_step("Шаг 4.3: Понижение Администратора до сотрудника", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees/edit", demote_payload, auth_headers, 200)

    # --- НОВЫЙ ШАГ: Получение списка всех сотрудников ---
    run_test_step("Шаг 5: Получение списка ВСЕХ сотрудников фирмы", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees",
                  {}, auth_headers, 200, method="GET")

    # --- Шаг 6: Удаление сотрудника ---
    delete_payload = {"user_id_to_delete": employee_id}
    run_test_step("Шаг 6: Удаление сотрудника из фирмы", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees/delete", delete_payload, auth_headers, 200)

    # --- Шаг 7: Проверка факта удаления ---
    run_test_step("Шаг 7: Проверка факта удаления (ожидается 404)", 
                  f"{API_MGMT_URL}/firms/{FIRM_ID}/employees?user_id_to_get={employee_id}",
                  {}, auth_headers, 404, method="GET")

    print("\n--- Тестирование успешно завершено ---")