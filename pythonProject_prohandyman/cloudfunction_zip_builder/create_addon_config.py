#!/usr/bin/env python3

import os
import json
import re
import posixpath
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, simpledialog
from colorama import init, Fore, Style

init(autoreset=True)

TICK = Fore.GREEN + "[OK]" + Style.RESET_ALL
CROSS = Fore.RED + "[FAIL]" + Style.RESET_ALL
DEFAULT_INITIAL_DIR = str(
    (Path(__file__).resolve().parents[2] / "obsidian_prohandyman" / "𝒇 Функции").resolve()
)


def to_windows_path(path_str):
    if not path_str:
        return None
    normalized = str(path_str).strip()
    match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", normalized)
    if not match:
        return None
    drive = match.group(1).upper()
    rest = match.group(2).replace("/", "\\")
    return f"{drive}:\\{rest}"


def to_wsl_path(path_str):
    if not path_str:
        return None
    normalized = str(path_str).strip().replace("\\", "/")
    match = re.match(r"^([a-zA-Z]):/(.*)$", normalized)
    if not match:
        return None
    drive = match.group(1).lower()
    rest = match.group(2)
    return f"/mnt/{drive}/{rest}"


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
    source_path_str = str(Path(source_path).expanduser().resolve())
    config_dir = Path(__file__).resolve().parent / "addons" / "dirs"
    source_relative_path = posixpath.normpath(
        os.path.relpath(source_path_str, start=str(Path(__file__).resolve().parent))
    ).replace("\\", "/")
    config = {
        "source_relative_path": source_relative_path,
        "target_name": target_name,
        "description": (
            f"Взять папку по относительному пути {source_relative_path} "
            f"и вставить в корень каждого ZIP с переименованием в '{target_name}'"
        ),
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
    config_dir = Path(__file__).resolve().parent / "addons" / "dirs"
    config_dir.mkdir(parents=True, exist_ok=True)
    
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
