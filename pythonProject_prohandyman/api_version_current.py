import json
import os
import re
import sys
import requests
from colorama import init, Fore, Style

# Инициализируем colorama для цветного вывода
init(autoreset=True)

# --- Конфигурация ---
API_VERSION_URL = "https://d5d2vigu6hojb3u0fthu.lievo6ut.apigw.yandexcloud.net/current"
DEFAULT_HEADERS = {"Accept": "application/json"}
EXPECTED_VERSION = os.getenv("EXPECTED_APP_VERSION")
SEMVER_WITH_BUILD = re.compile(r"^\d+\.\d+\.\d+(?:\+\d+)?$")

# --- Символы статуса ---
TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL
INFO = Fore.CYAN + "→" + Style.RESET_ALL


def run_get_step(title: str, url: str, headers: dict, expected_status: int = 200):
    """Отправляет GET-запрос и возвращает ответ при успешном статусе."""
    print(f"{Style.BRIGHT}► {title}", end=" ... ")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == expected_status:
            print(f"{TICK} (Статус: {response.status_code})")
            return response

        print(f"{CROSS} (Ожидался статус {expected_status}, получен {response.status_code})")
        print(Fore.RED + "  Текст ошибки:")
        try:
            print(Fore.RED + json.dumps(response.json(), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(Fore.RED + response.text)
        return None
    except requests.exceptions.RequestException as exc:
        print(f"{CROSS} (Исключение во время запроса)")
        print(Fore.RED + f"  Текст ошибки: {exc}")
        return None


if __name__ == "__main__":
    print("\n--- Тестирование Version API ---\n")

    # Шаг 1: Получение версии приложения
    response = run_get_step(
        "Шаг 1: Запрос текущей версии приложения",
        API_VERSION_URL,
        DEFAULT_HEADERS,
        200,
    )
    if not response:
        sys.exit(f"\n{CROSS} Критическая ошибка: запрос к Version API завершился неуспешно.")

    # Шаг 2: Валидация структуры ответа
    print(f"\n{Style.BRIGHT}► Шаг 2: Валидация структуры ответа")
    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        print(f"  {CROSS} Ответ не является корректным JSON: {exc}")
        sys.exit(f"\n{CROSS} Тестирование прервано.")

    version = payload.get("version")
    if not isinstance(version, str):
        print(f"  {CROSS} Поле 'version' отсутствует или имеет некорректный тип: {type(version).__name__}")
        sys.exit(f"\n{CROSS} Тестирование прервано.")

    print(f"  {INFO} Версия из ответа: {Style.BRIGHT}{version}{Style.RESET_ALL}")

    if EXPECTED_VERSION:
        print(f"  {INFO} Ожидаемая версия из переменной окружения: {Style.BRIGHT}{EXPECTED_VERSION}{Style.RESET_ALL}")
        if version == EXPECTED_VERSION:
            print(f"  {TICK} Версия совпадает с ожидаемой.")
        else:
            print(f"  {CROSS} Полученная версия не совпадает с ожидаемой.")
            sys.exit(f"\n{CROSS} Тестирование завершено с ошибкой.")

    # Шаг 3: Проверка формата версии
    print(f"\n{Style.BRIGHT}► Шаг 3: Проверка формата версии (SemVer+build)")
    if SEMVER_WITH_BUILD.fullmatch(version):
        print(f"  {TICK} Формат версии валиден.")
    else:
        print(f"  {CROSS} Неверный формат версии. Ожидался SemVer с опциональным '+build'.")
        sys.exit(f"\n{CROSS} Тестирование завершено с ошибкой.")

    print("\n--- Тестирование успешно завершено ---")
