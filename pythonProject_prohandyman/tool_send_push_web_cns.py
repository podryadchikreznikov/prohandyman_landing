import boto3
import json
import sys
import tkinter as tk
from tkinter import scrolledtext, messagebox
from botocore.exceptions import ClientError
import os
from typing import Dict

# -------------------------------------------
# ▼▼▼ КОНФИГУРАЦИЯ ▼▼▼
# -------------------------------------------
YC_KEY_ID_ENV = "YC_KEY_ID"
YC_SECRET_KEY_ENV = "YC_SECRET_KEY"
PLATFORM_APP_ARN_ENV = "YC_PLATFORM_APP_ARN"
NOTIF_TITLE = "Финальная отправка"
NOTIF_BODY = "Этот push был отправлен с использованием корректной логики ПЕРЕСОЗДАНИЯ эндпоинта. ✅"
YC_ENDPOINT_URL = "https://notifications.yandexcloud.net"
YC_REGION = "ru-central1"
PUSH_SUB_SAVE_FILE = "last_push_subscription.json"
ENDPOINT_ARN_SAVE_FILE = "last_endpoint_arn.txt"

# -------------------------------------------
# ▼▼▼ ЗАГРУЗКА СЕКРЕТОВ ИЗ ОКРУЖЕНИЯ ▼▼▼
# -------------------------------------------


def _load_yc_credentials() -> Dict[str, str]:
    """Загружает реквизиты Yandex Cloud из переменных окружения."""
    required = {
        YC_KEY_ID_ENV: "Yandex Cloud access key ID",
        YC_SECRET_KEY_ENV: "Yandex Cloud secret access key",
        PLATFORM_APP_ARN_ENV: "Yandex Cloud platform application ARN",
    }
    missing = [env for env in required if not os.environ.get(env)]
    if missing:
        missing_vars = ", ".join(missing)
        raise RuntimeError(
            f"Отсутствуют обязательные переменные окружения: {missing_vars}. "
            f"Добавьте их в .env (не коммить) или экспортируйте перед запуском."
        )

    return {
        "access_key_id": os.environ[YC_KEY_ID_ENV],
        "secret_access_key": os.environ[YC_SECRET_KEY_ENV],
        "platform_app_arn": os.environ[PLATFORM_APP_ARN_ENV],
    }



# -------------------------------------------
# ▲▲▲ БОЛЬШE НИЧЕГО РЕДАКТИРОВАТЬ НЕ НУЖНО ▲▲▲
# -------------------------------------------

def save_text_to_file(filename: str, content: str):
    """Универсальная функция сохранения текста в файл."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✓ Данные сохранены в файл: {filename}")
    except Exception as e:
        print(f"[Предупреждение] Не удалось сохранить файл {filename}: {e}", file=sys.stderr)


def read_text_from_file(filename: str) -> str:
    """Универсальная функция чтения текста из файла."""
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[Предупреждение] Не удалось прочитать файл {filename}: {e}")
    return ""


def get_json_from_gui():
    result_json = [None]
    initial_text = read_text_from_file(PUSH_SUB_SAVE_FILE)
    root = tk.Tk()
    root.title("Вставьте JSON от Flutter")
    root.geometry("450x350")
    root.attributes('-topmost', True)

    def on_submit():
        pasted_text = text_area.get("1.0", "end-1c").strip()
        if pasted_text:
            save_text_to_file(PUSH_SUB_SAVE_FILE, pasted_text)
            result_json[0] = pasted_text
        root.destroy()

    tk.Label(root, text="Вставьте PushSubscription JSON из Flutter-приложения:", wraplength=400).pack(pady=10)
    text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=12, width=50)
    text_area.pack(pady=5, padx=10, expand=True, fill='both')
    text_area.insert(tk.END, initial_text)
    text_area.focus_set()
    context_menu = tk.Menu(root, tearoff=0)
    context_menu.add_command(label="Вырезать", command=lambda: text_area.event_generate("<<Cut>>"))
    context_menu.add_command(label="Копировать", command=lambda: text_area.event_generate("<<Copy>>"))
    context_menu.add_command(label="Вставить", command=lambda: text_area.event_generate("<<Paste>>"))
    context_menu.add_separator()
    context_menu.add_command(label="Выделить всё", command=lambda: text_area.tag_add("sel", "1.0", "end"))

    def show_context_menu(event): context_menu.tk_popup(event.x_root, event.y_root)

    text_area.bind("<Button-3>", show_context_menu)
    tk.Button(root, text="Обработать эндпоинт и отправить", command=on_submit).pack(pady=15)
    root.mainloop()
    return result_json[0]


def process_and_send(push_subscription_json: str):
    """
    [ПЕРЕПИСАНО] Главная функция с правильной логикой удаления и создания.
    """
    try:
        json.loads(push_subscription_json)
    except json.JSONDecodeError:
        messagebox.showerror("Ошибка", "Введенный текст не является корректным JSON.")
        return

    try:
        creds = _load_yc_credentials()
    except RuntimeError as cred_error:
        messagebox.showerror("Нет доступа",
                             f"{cred_error}\n\n"
                             "Пример: export YC_KEY_ID=... && export YC_SECRET_KEY=...")
        return

    client = boto3.client(
        "sns",
        region_name=YC_REGION,
        endpoint_url=YC_ENDPOINT_URL,
        aws_access_key_id=creds["access_key_id"],
        aws_secret_access_key=creds["secret_access_key"],
        verify=False
    )

    endpoint_arn = read_text_from_file(ENDPOINT_ARN_SAVE_FILE)
    needs_recreation = not endpoint_arn

    if endpoint_arn and not needs_recreation:
        try:
            print(f"\n--- ШАГ 1: Проверка существующего эндпоинта ---")
            print(f"→ Запрос GetEndpointAttributes для: {endpoint_arn}")
            attrs = client.get_endpoint_attributes(EndpointArn=endpoint_arn)['Attributes']

            # Сравниваем токены, предварительно распарсив их
            token_is_different = False
            try:
                current_token_dict = json.loads(attrs.get('Token', '{}'))
                new_token_dict = json.loads(push_subscription_json)
                if current_token_dict != new_token_dict:
                    token_is_different = True
            except (json.JSONDecodeError, AttributeError):
                token_is_different = True

            print(
                f"✓ Эндпоинт найден. Статус Enabled: {attrs.get('Enabled')}. Токен совпадает: {not token_is_different}")

            if attrs.get('Enabled').lower() == 'false' or token_is_different:
                print("→ Эндпоинт требует пересоздания (отключен или токен устарел).")
                print(f"→ Запрос DeleteEndpoint для: {endpoint_arn}")
                client.delete_endpoint(EndpointArn=endpoint_arn)
                print("✓ Старый эндпоинт удален.")
                needs_recreation = True

        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFound':
                print("✗ Сохраненный эндпоинт не найден. Будет создан новый.")
                needs_recreation = True
            else:
                raise

    if needs_recreation:
        try:
            print(f"\n--- ШАГ 1А: Создание нового эндпоинта ---")
            print(f"→ Запрос CreatePlatformEndpoint...")
            response_create = client.create_platform_endpoint(
                PlatformApplicationArn=creds["platform_app_arn"],
                Token=push_subscription_json,
            )
            endpoint_arn = response_create["EndpointArn"]
            print(f"✓ Новый эндпоинт успешно создан: {endpoint_arn}")
            save_text_to_file(ENDPOINT_ARN_SAVE_FILE, endpoint_arn)
        except ClientError as e:
            messagebox.showerror("Ошибка API при создании",
                                 f"Код: {e.response['Error']['Code']}\n{e.response['Error']['Message']}")
            return

    try:
        print(f"\n--- ШАГ 2: Отправка уведомления ---")
        print(f"→ Запрос Publish на эндпоинт: {endpoint_arn}")
        web_payload = {"notification": {"title": NOTIF_TITLE, "body": NOTIF_BODY}}
        message_to_publish = {"default": NOTIF_BODY, "WEB": json.dumps(web_payload)}

        response_publish = client.publish(
            TargetArn=endpoint_arn,
            Message=json.dumps(message_to_publish),
            MessageStructure="json",
        )
        print(f"✓ Уведомление успешно отправлено. Message ID: {response_publish['MessageId']}")
        messagebox.showinfo("Успех", f"Уведомление отправлено!\n\nMessage ID: {response_publish['MessageId']}")

    except ClientError as e:
        messagebox.showerror("Ошибка API при отправке",
                             f"Код: {e.response['Error']['Code']}\n{e.response['Error']['Message']}")


if __name__ == "__main__":
    user_json = get_json_from_gui()
    if user_json:
        process_and_send(user_json)
    else:
        print("→ Операция отменена пользователем.")