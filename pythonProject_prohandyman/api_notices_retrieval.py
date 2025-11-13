# test_notices_api.py
import requests
import json
import sys
from datetime import datetime
from colorama import init, Fore, Style

# Инициализируем colorama
init(autoreset=True)

# --- Конфигурация ---
API_AUTH_URL = "https://d5dppitf9vbj18mkmls1.9bgyfspn.apigw.yandexcloud.net/login"
API_NOTICES_URL = "https://d5dqe519ci8oku6g0075.bixf7e87.apigw.yandexcloud.net/notices"

LOGIN_PAYLOAD = {"email": "ctac23062006@gmail.com", "password": "458854Mm"}
DEFAULT_HEADERS = {"Content-Type": "application/json"}

# --- Символы для вывода ---
TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL
INFO = Fore.CYAN + "→" + Style.RESET_ALL

def run_request(title: str, method: str, url: str, payload: dict, headers: dict, expected_status: int):
    """Универсальная функция для выполнения POST или GET запроса."""
    print(f"{Style.BRIGHT}► {title}", end=" ... ")
    try:
        if method.upper() == 'POST':
            response = requests.post(url, json=payload, headers=headers, timeout=15)
        else: # По умолчанию GET
            response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == expected_status:
            print(f"{TICK} (Статус: {response.status_code})")
            return response
        else:
            print(f"{CROSS} (Ожидался статус {expected_status}, получен {response.status_code})")
            print(Fore.RED + "  Текст ошибки:")
            try:
                print(Fore.RED + json.dumps(response.json(), indent=2, ensure_ascii=False))
            except json.JSONDecodeError:
                print(Fore.RED + response.text)
            return None
    except requests.exceptions.RequestException as e:
        print(f"{CROSS} (Исключение во время запроса)")
        print(Fore.RED + f"  Текст ошибки: {e}")
        return None

if __name__ == "__main__":
    print("\n--- Тестирование эндпоинта /notices ---\n")

    # Шаг 1: Аутентификация для получения токена
    login_response = run_request(
        "Шаг 1: Получение JWT токена",
        'POST',
        API_AUTH_URL,
        LOGIN_PAYLOAD,
        DEFAULT_HEADERS,
        200
    )
    if not login_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось войти в систему. Тестирование прервано.")

    jwt_token = login_response.json().get("token")
    auth_headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {jwt_token}"}

    # Шаг 2: Запрос списка уведомлений
    get_notices_url = f"{API_NOTICES_URL}?page=0&get_archived=false"
    get_response = run_request(
        "Шаг 2: Запрос списка уведомлений (page=0)",
        'GET',
        get_notices_url,
        None, # GET-запрос не имеет тела
        auth_headers,
        200
    )
    if not get_response:
        sys.exit(f"\n{CROSS} Критическая ошибка: не удалось получить список уведомлений.")

    # Шаг 3: Парсинг и отображение результата
    print(f"\n{Style.BRIGHT}► Шаг 3: Анализ полученных данных")
    try:
        response_data = get_response.json()
        metadata = response_data.get('metadata', {})
        notices = response_data.get('data', [])

        print(f"  {INFO} Всего уведомлений найдено: {metadata.get('total')}")
        print(f"  {INFO} Текущая страница: {metadata.get('page')}")
        print(f"  {INFO} Всего страниц: {metadata.get('pages')}")
        print(f"  {INFO} Количество уведомлений на странице: {len(notices)}")

        if notices:
            print(f"\n  {Style.BRIGHT}Первые 5 уведомлений:")
            for notice in notices[:5]:
                # Конвертируем timestamp (в микросекундах) в читаемую дату
                ts = notice.get('created_at', 0)
                date_str = datetime.fromtimestamp(ts / 1_000_000).strftime('%Y-%m-%d %H:%M:%S')
                print(f"    - '{notice.get('title')}' (Создано: {date_str})")

    except (json.JSONDecodeError, KeyError) as e:
        print(f"  {CROSS} Не удалось разобрать ответ от сервера: {e}")

    print("\n--- Тестирование завершено ---")