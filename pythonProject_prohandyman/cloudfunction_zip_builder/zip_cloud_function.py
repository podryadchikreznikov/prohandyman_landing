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
import json
from colorama import init, Fore, Style

init(autoreset=True)

TICK = Fore.GREEN + "[OK]" + Style.RESET_ALL
CROSS = Fore.RED + "[FAIL]" + Style.RESET_ALL
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
            base = re.split(r'\s-\s', base, 1)[0]
            new_name = base
            dest_file = dest_path / new_name
        else:
            dest_file = dest_path / src_path.name
        
        with open(dest_file, 'w', encoding='utf-8') as f:
            f.write(python_code)
        
        return dest_file
    else:
        if re.search(r'\s-\s', src_path.name):
            return None
        dest_file = dest_path / src_path.name
        shutil.copy2(src_path, dest_file)
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
            sub_files = process_directory(item, new_subdir)
            processed_files.extend(sub_files)
    
    return processed_files


def copy_additions(additions_dir, dest_dir):
    if not additions_dir.exists():
        return []
    
    copied_files = []
    for root, dirs, files in os.walk(additions_dir):
        rel_root = Path(root).relative_to(additions_dir)
        target_root = dest_dir / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        
        for filename in files:
            if filename.endswith('.json'):
                continue
            src_file = Path(root) / filename
            dest_file = target_root / filename
            if dest_file.exists():
                continue
            shutil.copy2(src_file, dest_file)
            copied_files.append(dest_file)
    
    return copied_files


def load_addon_configs(addons_dir):
    configs = []
    if not addons_dir.exists():
        return configs

    for json_file in addons_dir.glob('addon_*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                configs.append(config)
        except Exception as e:
            print(f"  {CROSS} Не удалось загрузить {json_file.name}: {e}")

    return configs


def copy_addon_folders(addon_configs, dest_dir):
    for config in addon_configs:
        source_path = Path(config.get('source_path', ''))
        target_name = config.get('target_name')

        if not source_path.exists() or not target_name:
            print(f"  {CROSS} Пропущено дополнение: {config}")
            continue

        target_path = dest_dir / target_name

        try:
            if target_path.exists():
                shutil.rmtree(target_path)
            shutil.copytree(source_path, target_path)
        except Exception as e:
            print(f"  {CROSS} Ошибка дополнения '{target_name}': {e}")


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
    print("\nШаг 1: Выбор базовой папки...", end=" ")
    base_folder = select_folder()
    if not base_folder:
        print(f"{CROSS} Папка не выбрана")
        return
    base_path = Path(base_folder)
    if not base_path.exists():
        print(f"{CROSS} Папка не существует: {base_folder}")
        return
    print(f"{TICK} {base_path.name}")
    
    zip_dir = Path(__file__).parent / "zips"
    zip_dir.mkdir(exist_ok=True)
    
    addons_dir = Path(__file__).parent / "addons"
    
    addon_configs = load_addon_configs(addons_dir)

    print("\nШаг 2: Дополнения...")
    if addon_configs:
        for config in addon_configs:
            print(f"  + {config.get('target_name', '?')}")
    else:
        print("  (нет)")

    print("\nШаг 3: Сборка функций...")
    built = 0
    for func_dir in sorted([p for p in base_path.iterdir() if p.is_dir()]):
        code_dirs = [p for p in func_dir.iterdir() if p.is_dir() and p.name.startswith("Python код - ")]
        if not code_dirs:
            continue
        for code_dir in code_dirs:
            print(f"  {func_dir.name}...", end=" ")
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                work_dir = temp_path / "cloud_function"
                work_dir.mkdir()
                process_directory(code_dir, work_dir)
                copy_additions(addons_dir, work_dir)
                copy_addon_folders(addon_configs, work_dir)
                zip_name = f"{func_dir.name}.zip"
                zip_path = zip_dir / zip_name
                try:
                    create_zip_archive(work_dir, zip_path)
                    size = zip_path.stat().st_size
                    print(f"{TICK} {size} байт")
                    built += 1
                except Exception as e:
                    print(f"{CROSS} {e}")
    
    if built == 0:
        print(f"{CROSS} Функции не найдены")
        return
    
    print(f"\nГотово: {built} архивов")
    print(f"Папка: {zip_dir}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{CROSS} Отменено")
    except Exception as e:
        print(f"\n{CROSS} Ошибка: {e}")
    
    input()
