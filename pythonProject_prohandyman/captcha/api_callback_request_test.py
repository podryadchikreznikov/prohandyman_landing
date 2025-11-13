# api_callback_request_test.py / test_callback_request.py
import json
import os
import sys
import threading
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, List

import requests
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = os.getenv(
    "CALLBACK_REQUEST_API_URL",
    "https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net",
).rstrip("/")

EXPECTED_SUCCESS_STATUS = int(os.getenv("CALLBACK_REQUEST_EXPECTED_STATUS", "200"))
SMARTCAPTCHA_CLIENT_KEY_DEFAULT = "ysc1_JMJcAAfPce436nv20qcDpdMChASo4m5y2phUgeFLbfc3400a"

TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL


def _pretty(data: Any) -> str:
    if data is None:
        return "<empty>"
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        return str(data)


def make_headers(token: Optional[str]) -> Dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "X-Correlation-Id": str(uuid.uuid4()),
    }
    if token:
        headers["SmartCaptcha-Token"] = token
    return headers


def run_step(
    title: str,
    path: str,
    payload: Optional[Dict[str, Any]],
    expected_statuses: List[int],
    captcha_token: Optional[str],
) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}{path}"
    print(f"{Style.BRIGHT}→ {title}{Style.RESET_ALL}")
    print(Fore.BLUE + f"   POST {url}")
    if payload is not None:
        print(Fore.BLUE + f"   body = {_pretty(payload)}")

    kwargs: Dict[str, Any] = {"headers": make_headers(captcha_token), "timeout": 20}
    if payload is not None:
        kwargs["json"] = payload

    try:
        response = requests.post(url, **kwargs)
    except requests.RequestException as exc:
        print(f"   {CROSS} ошибка запроса: {exc}")
        return None

    if response.status_code in expected_statuses:
        print(f"   {TICK} {response.status_code}")
        try:
            data = _safe_json(response)
            if data:
                print(Fore.GREEN + f"   тело = {_pretty(data)}")
            return data
        except Exception:
            return None
    else:
        print(f"   {CROSS} ожидали {expected_statuses}, получили {response.status_code}")
        try:
            print(Fore.RED + f"   тело = {_pretty(_safe_json(response))}")
        except Exception:
            pass
        return None


def _safe_json(response: requests.Response) -> Optional[Dict[str, Any]]:
    try:
        return response.json()
    except json.JSONDecodeError:
        return None


class _CaptchaTokenServer(HTTPServer):
    def __init__(self, server_address, handler_class, client_key: str):
        super().__init__(server_address, handler_class)
        self.client_key = client_key
        self.token: Optional[str] = None
        self.token_event = threading.Event()


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <title>SmartCaptcha Token</title>
  <script src="https://captcha-api.yandex.ru/captcha.js" defer></script>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 30px; }}
    #status {{ margin-top: 20px; color: #444; }}
  </style>
</head>
<body>
  <h2>Пройдите SmartCaptcha</h2>
  <div id="captcha-container"></div>
  <p id="status">Ожидаю прохождения капчи.</p>
  <script>
    document.addEventListener('DOMContentLoaded', function() {{
        function initCaptcha() {{
            if (!window.smartCaptcha) {{
                document.getElementById('status').innerText = 'Не удалось загрузить SmartCaptcha';
                return;
            }}
            window.smartCaptcha.render('captcha-container', {{
                sitekey: '{sitekey}',
                callback: function(token) {{
                    document.getElementById('status').innerText = 'Токен получен, отправляю.';
                    fetch('/token', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{token}})
                    }}).then(function() {{
                        document.getElementById('status').innerText = 'Токен передан тесту. Можно закрыть окно.';
                    }}).catch(function() {{
                        document.getElementById('status').innerText = 'Не удалось отправить токен на локальный сервер.';
                    }});
                }}
            }});
        }}
        if (window.smartCaptcha && window.smartCaptcha.render) {{
            initCaptcha();
        }} else {{
            window.onload = initCaptcha;
        }}
    }});
  </script>
</body>
</html>
"""


class CaptchaHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            html = HTML_TEMPLATE.format(sitekey=self.server.client_key)
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/token":
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {}
        token = (payload or {}).get("token")
        if token:
            self.server.token = token
            self.server.token_event.set()
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # глушим стандартный лог http.server
        return


def obtain_smartcaptcha_token() -> Optional[str]:
    env_token = os.getenv("CALLBACK_REQUEST_SMARTCAPTCHA_TOKEN")
    if env_token:
        print(Fore.CYAN + "   SmartCaptcha token взят из переменной окружения\n")
        return env_token.strip()

    client_key = os.getenv("SMARTCAPTCHA_CLIENT_KEY", SMARTCAPTCHA_CLIENT_KEY_DEFAULT).strip()
    if not client_key:
        sys.exit(f"{CROSS} Не указан SMARTCAPTCHA_CLIENT_KEY")

    port = int(os.getenv("SMARTCAPTCHA_LOCAL_PORT", "8765"))
    server = _CaptchaTokenServer(("127.0.0.1", port), CaptchaHandler, client_key)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}/"
    print(Fore.YELLOW + f"   Открылось окно {url} — пройдите SmartCaptcha.")
    webbrowser.open(url)

    if not server.token_event.wait(timeout=180):
        server.shutdown()
        server.server_close()
        sys.exit(f"{CROSS} Токен SmartCaptcha не получен (таймаут).")

    token = server.token
    server.shutdown()
    server.server_close()
    print(Fore.GREEN + "   Токен SmartCaptcha получен.\n")
    return token


if __name__ == "__main__":
    print(f"\n--- Тест API callback-request ({BASE_URL}) ---")

    # 0) Проверка authorizer / security-scheme:
    #    БЕЗ токена капчи (captcha_token=None) — ожидаем 401 или 403 от Gateway
    run_step(
        "Авторизация: без токена капчи (ожидаем 401 или 403)",
        "/callback/request",
        payload={"comment": "тест без токена"},
        expected_statuses=[401, 403],
        captcha_token=None,
    )

    # 1) Проверка валидации (нет phone/email) — 400 от функции callback-request
    #    Для этого шага НУЖЕН СВЕЖИЙ ТОКЕН
    print(Fore.CYAN + "\n--- Получение токена для теста валидации ---")
    token_for_validation_test = obtain_smartcaptcha_token()
    step1_result = run_step(
        "Проверка валидации (нет phone/email)",
        "/callback/request",
        payload={"comment": "тест"},
        expected_statuses=[400],
        captcha_token=token_for_validation_test,
    )
    if step1_result is None:
        sys.exit(f"{CROSS} критическая ошибка проверки валидации")

    # 2) Успешный кейс: валидные данные + токен
    #    Для этого шага НУЖЕН ЕЩЕ ОДИН СВЕЖИЙ ТОКЕН
    print(Fore.CYAN + "\n--- Получение токена для успешного теста ---")
    token_for_success_test = obtain_smartcaptcha_token()
    valid_payload = {
        "phone_number": os.getenv("CALLBACK_REQUEST_TEST_PHONE", "+7 912 047-09-57"),
        "user_name": os.getenv("CALLBACK_REQUEST_TEST_NAME", "Tester"),
        "comment": os.getenv("CALLBACK_REQUEST_TEST_COMMENT", "Тестовое уведомление"),
    }
    email = os.getenv("CALLBACK_REQUEST_TEST_EMAIL", "").strip()
    if email:
        valid_payload["email"] = email

    run_step(
        "Отправка заявки (валидные данные)",
        "/callback/request",
        payload=valid_payload,
        expected_statuses=[EXPECTED_SUCCESS_STATUS],
        captcha_token=token_for_success_test,
    )