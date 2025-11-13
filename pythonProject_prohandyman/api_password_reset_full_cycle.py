# test_password_reset.py
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
# Пользователь, для которого будет производиться сброс пароля
TEST_EMAIL = "ctacnazarov23@gmail.com"
# Пароль, который будет установлен ВРЕМЕННО
NEW_PASSWORD = "NewSecurePassword123!"
# Пароль, который будет восстановлен в конце теста для чистоты
ORIGINAL_PASSWORD = "458854Mm"

# Символы для статуса
TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL
INFO = Fore.CYAN + "→" + Style.RESET_ALL


def run_test_step(title: str, url: str, payload: dict, headers: dict, expected_status: int):
    """Выполняет один шаг теста, выводит результат и возвращает ответ в случае успеха."""
    print(f"{Style.BRIGHT}► {title}", end=" ... ")

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)

        if response.status_code == expected_status:
            print(f"{TICK} (Статус: {response.status_code})")
            return response
        else:
            print(f"{CROSS} (Ожидался статус {expected_status}, получен {response.status_code})")
            print(Fore.RED + "  Текст ошибки:")
            try:
                error_json = response.json()
                print(Fore.RED + json.dumps(error_json, indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(Fore.RED + response.text)
            return None

    except requests.exceptions.RequestException as e:
        print(f"{CROSS} (Исключение во время запроса)")
        print(Fore.RED + f"  Текст ошибки: {e}")
        return None


if __name__ == "__main__":
    print("\n--- Начало полного цикла тестирования сброса пароля ---\n")

    # --- Шаг 1: Запрос на сброс пароля ---
    request_payload = {"email": TEST_EMAIL}
    run_test_step(
        "Шаг 1: Запрос на сброс пароля",
        f"{BASE_URL}/password/request-reset",
        request_payload,
        DEFAULT_HEADERS,
        expected_status=200
    )

    # --- Шаг 1.5: Ручной ввод хеша из письма ---
    print(f"\n{Style.BRIGHT}{Fore.YELLOW}ОЖИДАНИЕ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ:{Style.RESET_ALL}")
    print(f"{INFO} Пожалуйста, проверьте почту {TEST_EMAIL}.")
    print(f"{INFO} Скопируйте хеш-ключ из письма и вставьте его ниже.")
    password_hash_from_email = input(f"{Style.BRIGHT}Введите хеш-ключ и нажмите Enter: {Style.RESET_ALL}").strip()

    if not password_hash_from_email:
        sys.exit(f"\n{CROSS} Критическая ошибка: хеш-ключ не был введен. Тестирование прервано.")

    # --- Шаг 2: Негативный тест - попытка сброса с неверным хешем ---
    wrong_reset_payload = {
        "email": TEST_EMAIL,
        "new_password": NEW_PASSWORD,
        "current_password_hash": "this_is_a_deliberately_wrong_hash_12345"
    }
    run_test_step(
        "Шаг 2: Попытка сброса с неверным хешем (ожидается 401)",
        f"{BASE_URL}/password/reset",
        wrong_reset_payload,
        DEFAULT_HEADERS,
        expected_status=401
    )

    # --- Шаг 3: Позитивный тест - сброс пароля с корректным хешем ---
    correct_reset_payload = {
        "email": TEST_EMAIL,
        "new_password": NEW_PASSWORD,
        "current_password_hash": password_hash_from_email
    }
    reset_response = run_test_step(
        "Шаг 3: Сброс пароля с корректным хешем из письма",
        f"{BASE_URL}/password/reset",
        correct_reset_payload,
        DEFAULT_HEADERS,
        expected_status=200
    )
    if not reset_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось сбросить пароль. Тестирование прервано.")

    new_jwt_token = reset_response.json().get("token")
    print(f"{INFO} Пароль успешно сброшен. Получен новый JWT токен: ...{new_jwt_token[-15:]}")

    # --- Шаг 4: Верификация - вход с новым паролем ---
    login_with_new_pass_payload = {
        "email": TEST_EMAIL,
        "password": NEW_PASSWORD
    }
    run_test_step(
        "Шаг 4: Проверка входа с НОВЫМ паролем",
        f"{BASE_URL}/login",
        login_with_new_pass_payload,
        DEFAULT_HEADERS,
        expected_status=200
    )

    # --- Шаг 5 (Очистка): Возврат пароля к исходному состоянию ---
    print(f"\n{Style.BRIGHT}--- Шаг 5 (Очистка): Возврат пароля к исходному состоянию ---{Style.RESET_ALL}")
    cleanup_request_response = run_test_step(
        "Шаг 5.1: Повторный запрос на сброс",
        f"{BASE_URL}/password/request-reset",
        request_payload,
        DEFAULT_HEADERS,
        expected_status=200
    )
    if not cleanup_request_response:
        print(f"{Fore.RED}{Style.BRIGHT}ПРЕДУПРЕЖДЕНИЕ: Не удалось начать очистку. Пароль остался измененным на '{NEW_PASSWORD}'!{Style.RESET_ALL}")
    else:
        print(f"\n{Style.BRIGHT}{Fore.YELLOW}ОЖИДАНИЕ ДЕЙСТВИЯ ПОЛЬЗОВАТЕЛЯ (ОЧИСТКА):{Style.RESET_ALL}")
        print(f"{INFO} Пожалуйста, снова проверьте почту {TEST_EMAIL} и введите НОВЫЙ хеш-ключ.")
        cleanup_hash = input(f"{Style.BRIGHT}Введите хеш-ключ для очистки и нажмите Enter: {Style.RESET_ALL}").strip()

        if cleanup_hash:
            cleanup_reset_payload = {
                "email": TEST_EMAIL,
                "new_password": ORIGINAL_PASSWORD,
                "current_password_hash": cleanup_hash
            }
            run_test_step(
                "Шаг 5.2: Установка исходного пароля",
                f"{BASE_URL}/password/reset",
                cleanup_reset_payload,
                DEFAULT_HEADERS,
                expected_status=200
            )
            print(f"{INFO} Пароль успешно возвращен к исходному значению.")
        else:
            print(f"{Fore.RED}{Style.BRIGHT}ПРЕДУПРЕЖДЕНИЕ: Хеш для очистки не введен. Пароль остался измененным на '{NEW_PASSWORD}'!{Style.RESET_ALL}")

    print("\n--- Тестирование сброса пароля успешно завершено ---")