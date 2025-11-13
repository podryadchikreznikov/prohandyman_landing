# test_sequence_number_generator.py
import json
import os
import sys
import uuid
from typing import Any, Dict, Optional

import requests
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = os.getenv("SEQ_NUM_TESTS_API_URL", "https://tbd-seq-tests.apigw.yandexcloud.net").rstrip("/")
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "X-Correlation-Id": str(uuid.uuid4()),
}

TICK = Fore.GREEN + "✔" + Style.RESET_ALL
CROSS = Fore.RED + "✖" + Style.RESET_ALL


def _pretty(data: Any) -> str:
    if data is None:
        return "<empty>"
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)


def run_step(title: str, path: str, payload: Optional[Dict[str, Any]], expected_status: int) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}{path}"
    print(f"{Style.BRIGHT}→ {title}{Style.RESET_ALL}")
    print(Fore.BLUE + f"   POST {url}")
    if payload is not None:
        print(Fore.BLUE + f"   body = {_pretty(payload)}")
    kwargs = {"headers": DEFAULT_HEADERS, "timeout": 20}
    if payload is not None:
        kwargs["json"] = payload
    try:
        response = requests.post(url, **kwargs)
    except requests.RequestException as exc:
        print(f"   {CROSS} сеть недоступна: {exc}")
        return None

    if response.status_code != expected_status:
        print(f"   {CROSS} ожидали {expected_status}, получили {response.status_code}")
        print(Fore.RED + f"   тело = {_pretty(_safe_json(response))}")
        return None

    data = _safe_json(response)
    print(f"   {TICK} ответ {response.status_code}")
    if data:
        print(Fore.GREEN + f"   тело = {_pretty(data)}")
    return data


def _safe_json(response: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        return response.json()
    except json.JSONDecodeError:
        return None


def ensure_status(data: Optional[Dict[str, Any]], expected_state: str) -> None:
    if not data:
        sys.exit(f"{CROSS} критическая ошибка: пустой ответ от API")
    actual = data.get("status")
    if actual != expected_state:
        sys.exit(f"{CROSS} ожидали статус {expected_state}, получили {actual}")


if __name__ == "__main__":
    print("\n--- Проверяем ✳️🔢 sequence-number-generator через tests API ---")
    print(Fore.YELLOW + f"   BASE_URL = {BASE_URL}\n")

    entity_type = os.getenv("SEQ_NUM_TEST_ENTITY", "test-seq")
    shared_uuid = os.getenv("SEQ_NUM_TEST_UUID") or str(uuid.uuid4())
    print(Fore.CYAN + f"   entity_type = {entity_type}")
    print(Fore.CYAN + f"   uuid        = {shared_uuid}\n")

    # Step 1: позитивный вызов через /sequence-number/tests/new
    new_payload = {"entity_type": entity_type, "uuid": shared_uuid}
    step1 = run_step(
        "Сценарий NEW",
        "/sequence-number/tests/new",
        new_payload,
        expected_status=200,
    )
    ensure_status(step1, "NEW")

    # Step 2: повторяем тот же payload, ожидаем EXISTING
    step2 = run_step(
        "Повторный вызов (должен быть EXISTING)",
        "/sequence-number/tests/existing",
        new_payload,
        expected_status=200,
    )
    ensure_status(step2, "EXISTING")

    # Step 3: негативный сценарий с плохим UUID (используем специализированную точку)
    run_step(
        "Неверный UUID (ожидаем 400)",
        "/sequence-number/tests/invalid-uuid",
        payload=None,
        expected_status=400,
    )

    # Step 4: проверяем валидацию тела на основной точке
    run_step(
        "Пустой body на /sequence-number (ожидаем 400)",
        "/sequence-number",
        payload={},
        expected_status=400,
    )

    print(f"\n{TICK} smoke-сценарии завершены успешно")
