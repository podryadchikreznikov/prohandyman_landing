#!/usr/bin/env python3

import os
import re
import zipfile
import tempfile
import shutil
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import sys
from colorama import init, Fore, Style

init(autoreset=True)

TICK = Fore.GREEN + "✓" + Style.RESET_ALL
CROSS = Fore.RED + "✗" + Style.RESET_ALL
DEFAULT_INITIAL_DIR = r"c:\\FlutterProjects\\renzikov_hub\\obsidian_reznikov\\𝒇 Функции"


def extract_python_from_markdown(content):
    pattern = r'```python\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)
    
    if matches:
        return '\n'.join(matches)
    
    lines = content.split('\n')
    python_lines = []
    
    for line in lines:
        if line.strip().startswith('```') or line.strip().startswith('#'):
            continue
        python_lines.append(line)
    
    return '\n'.join(python_lines)


def process_file(src_path, dest_path):
    if src_path.suffix.lower() == '.md':
        with open(src_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        python_code = extract_python_from_markdown(content)
        
        if src_path.name.endswith('.md'):
            base = src_path.stem
            base = re.sub(r'\s*-\s*✳️.*$', '', base)
            new_name = base
            dest_file = dest_path / new_name
        else:
            dest_file = dest_path / src_path.name
        
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(python_code)
        
        print(f"{TICK} Извлечен Python код: {src_path.name} -> {new_name}")
        return dest_file
    else:
        if re.search(r'\s-\s✳️', src_path.name):
            return None
        dest_file = dest_path / src_path.name
        shutil.copy2(src_path, dest_file)
        print(f"{TICK} Скопирован файл: {src_path.name}")
        return dest_file


def process_directory(src_dir, dest_dir):
    processed_files = []
    
    for item in src_dir.iterdir():
        if item.is_file():
            processed_file = process_file(item, dest_dir)
            if processed_file is not None:
                processed_files.append(processed_file)
        elif item.is_dir():
            new_subdir = dest_dir / item.name
            new_subdir.mkdir(exist_ok=True)
            print(f"{TICK} Создана директория: {item.name}")
            sub_files = process_directory(item, new_subdir)
            processed_files.extend(sub_files)
    
    return processed_files


def create_zip_archive(source_dir, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
    
    return zip_path


def select_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    folder_path = filedialog.askdirectory(title="Выберите папку '𝒇 Функции'", initialdir=DEFAULT_INITIAL_DIR)
    
    root.destroy()
    return folder_path


def main():
    print(f"{Fore.CYAN}🚀 Скрипт пакетной сборки CloudFunction → ZIP")
    print("=" * 50)
    
    print(f"\n{Style.BRIGHT}► Шаг 1: Выбор базовой папки '𝒇 Функции'...", end=" ")
    base_folder = select_folder()
    if not base_folder:
        print(f"{CROSS} Папка не выбрана")
        return
    base_path = Path(base_folder)
    if not base_path.exists():
        print(f"{CROSS} Папка не существует: {base_folder}")
        return
    print(f"{TICK} Выбрана: {base_path}")
    
    zip_dir = Path(__file__).parent / "zips"
    zip_dir.mkdir(exist_ok=True)
    
    print(f"\n{Style.BRIGHT}► Шаг 2: Поиск функций и сборка...")
    built = 0
    for func_dir in sorted([p for p in base_path.iterdir() if p.is_dir()]):
        code_dirs = [p for p in func_dir.iterdir() if p.is_dir() and p.name.startswith("Python код - ")]
        if not code_dirs:
            continue
        for code_dir in code_dirs:
            print(f"• {func_dir.name}")
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                work_dir = temp_path / "cloud_function"
                work_dir.mkdir()
                processed_files = process_directory(code_dir, work_dir)
                zip_name = f"{func_dir.name}.zip"
                zip_path = zip_dir / zip_name
                try:
                    create_zip_archive(work_dir, zip_path)
                    print(f"  {TICK} ZIP: {zip_name} ({zip_path.stat().st_size} байт)")
                    built += 1
                except Exception as e:
                    print(f"  {CROSS} Ошибка: {e}")
    
    if built == 0:
        print(f"{CROSS} Не найдено ни одной функции с папкой 'Python код - ...'")
        return
    
    print(f"\n{Fore.GREEN}🎉 Готово. Собрано архивов: {built}")
    print(f"📂 Папка с архивами: {zip_dir}")
    try:
        os.startfile(zip_dir)
        print(f"{TICK} Папка с архивами открыта")
    except:
        pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{CROSS} Операция отменена")
    except Exception as e:
        print(f"\n{CROSS} Ошибка: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{Style.DIM}Нажмите Enter для выхода...")
    input()
