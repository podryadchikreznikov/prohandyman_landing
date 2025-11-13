#!/usr/bin/env python3

import os
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, simpledialog
from colorama import init, Fore, Style

init(autoreset=True)

TICK = Fore.GREEN + "[OK]" + Style.RESET_ALL
CROSS = Fore.RED + "[FAIL]" + Style.RESET_ALL
DEFAULT_INITIAL_DIR = r"c:\\FlutterProjects\\renzikov_hub\\obsidian_reznikov\\𝒇 Функции"


def select_folder():
    """Открывает проводник для выбора папки"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    folder_path = filedialog.askdirectory(
        title="Выберите папку для добавления в ZIP", 
        initialdir=DEFAULT_INITIAL_DIR
    )
    
    root.destroy()
    return folder_path


def get_new_name():
    """Открывает диалоговое окно для ввода нового имени папки"""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    new_name = simpledialog.askstring(
        "Новое имя папки", 
        "Введите имя папки в ZIP-архиве:",
        parent=root
    )
    
    root.destroy()
    return new_name


def create_addon_config(source_path, target_name):
    """Создает JSON-конфигурацию для добавления папки"""
    config = {
        "source_path": source_path,
        "target_name": target_name,
        "description": f"Взять папку по пути {source_path} и вставить в корень каждого ZIP с переименованием в '{target_name}'"
    }
    return config


def save_config(config, config_dir):
    """Сохраняет конфигурацию в JSON файл"""
    filename = f"addon_{config['target_name'].replace(' ', '_').lower()}.json"
    config_path = config_dir / filename
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    return config_path


def main():
    print("Создание конфигурации дополнения")

    print("Папка...", end=" ")
    source_folder = select_folder()
    if not source_folder:
        print(f"{CROSS} Папка не выбрана")
        return
    
    source_path = Path(source_folder)
    if not source_path.exists():
        print(f"{CROSS} Папка не существует: {source_folder}")
        return
    
    print(f"{TICK} {source_path}")

    print("Имя...", end=" ")
    target_name = get_new_name()
    if not target_name:
        print(f"{CROSS} Имя не указано")
        return

    target_name = target_name.strip().replace('/', '_').replace('\\', '_')
    if not target_name:
        print(f"{CROSS} Недопустимое имя")
        return

    print(f"{TICK} {target_name}")

    print("Файл...", end=" ")
    config_dir = Path(__file__).parent / "addons"
    config_dir.mkdir(exist_ok=True)
    
    config = create_addon_config(str(source_path.absolute()), target_name)
    config_path = save_config(config, config_dir)
    
    print(f"{TICK} {config_path}")

    print("Готово")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{CROSS} Отменено")
    except Exception as e:
        print(f"\n{CROSS} Ошибка: {e}")
    
    input()
