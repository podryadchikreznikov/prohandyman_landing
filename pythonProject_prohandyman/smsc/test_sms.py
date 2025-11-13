import requests

LOGIN = "reznikov"
PASSWORD = "makakaskrasnoikakoi_A9986"
PHONE = "79097033965"
MESSAGE = "Hello world"

API_URL = "https://smsc.ru/sys/send.php"

params = {
    "login": LOGIN,
    "psw": PASSWORD,
    "phones": PHONE,
    "mes": MESSAGE,
    "fmt": 3  # Ответ в формате JSON
}

try:
    response = requests.get(API_URL, params=params)
    print("Статус код:", response.status_code)
    print("Ответ сервера:", response.text)
    if response.status_code == 200:
        print("✓ СМС отправлена успешно (виртуально, тестовый режим)!")
    else:
        print("✗ Ошибка при отправке")
except Exception as e:
    print(f"Ошибка подключения: {e}")