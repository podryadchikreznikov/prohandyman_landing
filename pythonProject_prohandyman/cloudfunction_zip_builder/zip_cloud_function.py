#!/usr/bin/env python3

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from colorama import init, Fore, Style

init(autoreset=True)

TICK = Fore.GREEN + "[OK]" + Style.RESET_ALL
CROSS = Fore.RED + "[FAIL]" + Style.RESET_ALL
DEFAULT_INITIAL_DIR = str(
    (Path(__file__).resolve().parents[2] / "obsidian_prohandyman" / "𝒇 Функции").resolve()
)
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
ZIPS_DIR = SCRIPT_DIR / "zips"
IGNORED_SORT_FILE_NAMES = {"schema_hashes.json"}
IGNORED_SORT_DIR_NAMES = {"__pycache__"}
IGNORED_TOP_LEVEL_DIR_NAMES = {"С ДРУГОГО ПРОЕКТА"}


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


def candidate_paths_for_current_platform(*raw_paths):
    candidates = []

    def add_candidate(value):
        if not value:
            return
        text = str(value).strip()
        if not text or text in candidates:
            return
        candidates.append(text)

    for raw in raw_paths:
        if not raw:
            continue
        add_candidate(raw)
        add_candidate(to_wsl_path(raw))
        add_candidate(to_windows_path(raw))

    return [Path(candidate).expanduser() for candidate in candidates]


def candidate_paths_from_workspace(raw_path):
    if not raw_path:
        return []

    raw = str(raw_path).strip().replace("\\", "/")
    markers = [
        f"/{WORKSPACE_ROOT.name}/",
        "/pythonProject/",
    ]
    suffixes = []

    for marker in markers:
        if marker in raw:
            suffix = raw.split(marker, 1)[1]
            if marker == f"/{WORKSPACE_ROOT.name}/":
                candidate = WORKSPACE_ROOT / suffix
            else:
                candidate = WORKSPACE_ROOT / marker.strip("/") / suffix
            suffixes.append(candidate)

    unique = []
    seen = set()
    for candidate in suffixes:
        text = str(candidate)
        if text in seen:
            continue
        seen.add(text)
        unique.append(candidate)
    return unique


def candidate_paths_from_script_dir(raw_path):
    if not raw_path:
        return []

    raw = str(raw_path).strip().replace("\\", "/")
    if not raw:
        return []

    candidate = (SCRIPT_DIR / raw).resolve()
    return [candidate]


def resolve_addon_source_path(config):
    configured = [
        config.get("source_relative_path"),
        config.get("source_path_windows") if os.name == "nt" else config.get("source_path_wsl"),
        config.get("source_path"),
        config.get("source_path_windows"),
        config.get("source_path_wsl"),
    ]

    for raw_path in configured:
        for candidate in candidate_paths_from_script_dir(raw_path):
            if candidate.exists():
                return candidate.resolve()

    for candidate in candidate_paths_for_current_platform(*configured):
        if candidate.exists():
            return candidate.resolve()

    for raw_path in configured:
        for candidate in candidate_paths_from_workspace(raw_path):
            if candidate.exists():
                return candidate.resolve()

    return None


def process_file(src_path, dest_path):
    if src_path.suffix.lower() == ".md":
        text = src_path.read_text(encoding="utf-8")
        match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
        if not match:
            raise RuntimeError(f"Не удалось извлечь python-код из markdown-исходника: {src_path}")
        target_name = re.split(r"\s-\s", src_path.name, maxsplit=1)[0].strip()
        if not target_name.endswith(".py"):
            raise RuntimeError(f"Недопустимое имя целевого python-файла для markdown-исходника: {src_path}")
        dest_file = dest_path / target_name
        dest_file.write_text(match.group(1), encoding="utf-8")
        return dest_file
    if re.search(r"\s-\s", src_path.name):
        raise RuntimeError(
            f"Легаси-имя файла с ' - ' недопустимо внутри 'Python код - ...': {src_path}"
        )
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
        in_config_dir = rel_root.parts and rel_root.parts[0] == "dirs"
        target_root = dest_dir / rel_root
        target_root.mkdir(parents=True, exist_ok=True)
        
        for filename in files:
            if in_config_dir and filename.endswith('.json'):
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
        source_path = resolve_addon_source_path(config)
        target_name = config.get('target_name')

        if source_path is None or not target_name:
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
    # compresslevel=1 noticeably speeds up packaging for repeated local builds.
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)
    
    return zip_path


def _escape_powershell_single_quoted(value):
    return str(value).replace("'", "''")


def move_files_to_windows_recycle_bin(paths):
    if not paths:
        return 0

    windows_paths = []
    for path in paths:
        candidate = Path(path)
        windows_path = str(candidate)
        if os.name != "nt":
            converted = to_windows_path(windows_path)
            windows_path = converted or windows_path
        if windows_path not in windows_paths:
            windows_paths.append(windows_path)

    quoted_paths = ", ".join(f"'{_escape_powershell_single_quoted(path)}'" for path in windows_paths)
    powershell_script = f"""
Add-Type -AssemblyName Microsoft.VisualBasic
$paths = @({quoted_paths})
foreach ($path in $paths) {{
    if (Test-Path -LiteralPath $path) {{
        [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
            $path,
            [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
            [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
        )
    }}
}}
"""

    subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", powershell_script],
        check=True,
    )
    return len(windows_paths)


def clear_old_zip_archives(zip_dir):
    existing_zips = sorted(path for path in zip_dir.glob("*.zip") if path.is_file())
    if not existing_zips:
        return 0
    return move_files_to_windows_recycle_bin(existing_zips)


def get_latest_source_mtime_ns(func_dir):
    latest_mtime_ns = func_dir.stat().st_mtime_ns

    for path in func_dir.rglob('*'):
        if any(part in IGNORED_SORT_DIR_NAMES for part in path.parts):
            continue
        if path.is_file() and path.name in IGNORED_SORT_FILE_NAMES:
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        if stat.st_mtime_ns > latest_mtime_ns:
            latest_mtime_ns = stat.st_mtime_ns

    return latest_mtime_ns


def sort_function_dirs(func_dirs):
    return sorted(func_dirs, key=lambda path: (-get_latest_source_mtime_ns(path), path.name.lower()))


def select_folder():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    folder_path = filedialog.askdirectory(title="Выберите папку '𝒇 Функции'", initialdir=DEFAULT_INITIAL_DIR)
    
    root.destroy()
    return folder_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--functions-root", help="Путь к папке с функциями")
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Не открывать диалог выбора папки; использовать только --functions-root",
    )
    return parser.parse_args()


def resolve_base_path(args):
    if args.functions_root:
        return Path(args.functions_root).expanduser().resolve()

    if args.no_ui:
        raise ValueError("В режиме --no-ui нужно обязательно передать --functions-root")

    print("\nШаг 1: Выбор базовой папки...", end=" ")
    base_folder = select_folder()
    if not base_folder:
        raise ValueError("Папка не выбрана")

    base_path = Path(base_folder)
    print(f"{TICK} {base_path.name}")
    return base_path


def run_schema_hashes(base_path):
    compute_script = SCRIPT_DIR.parent / "compute_contract_schema_hashes.py"
    if not compute_script.exists():
        raise FileNotFoundError(f"Не найден compute_contract_schema_hashes.py: {compute_script}")

    cmd = [
        sys.executable,
        str(compute_script),
        "--no-ui",
        "--functions-root",
        str(base_path),
    ]
    subprocess.run(cmd, check=True)


def main():
    args = parse_args()
    base_path = resolve_base_path(args)
    if not base_path.exists():
        print(f"{CROSS} Папка не существует: {base_path}")
        return
    if args.functions_root:
        print(f"\nШаг 1: Базовая папка... {TICK} {base_path}")

    func_dirs = [p for p in base_path.iterdir() if p.is_dir() and p.name not in IGNORED_TOP_LEVEL_DIR_NAMES]
    # Fix build order before schema hash regeneration mutates mtimes across many functions.
    func_dirs_sorted = sort_function_dirs(func_dirs)

    print("\nШаг 2: Пересчет schema hashes...")
    run_schema_hashes(base_path)
    print(f"  {TICK} schema_hashes.json обновлены")
    
    zip_dir = ZIPS_DIR
    zip_dir.mkdir(parents=True, exist_ok=True)

    print("\nШаг 3: Очистка старых zip...")
    recycled = clear_old_zip_archives(zip_dir)
    if recycled:
        print(f"  {TICK} Перемещено в корзину: {recycled}")
    else:
        print("  (старых zip нет)")
    
    addons_dir = SCRIPT_DIR / "addons"
    addons_dirs_dir = addons_dir / "dirs"
    
    addon_configs = load_addon_configs(addons_dirs_dir)

    print("\nШаг 4: Дополнения...")
    if addon_configs:
        for config in addon_configs:
            print(f"  + {config.get('target_name', '?')}")
    else:
        print("  (нет)")

    print("\nШаг 5: Сборка функций...")
    built = 0

    for func_dir in func_dirs_sorted:
        code_dirs = [p for p in func_dir.iterdir() if p.is_dir() and p.name.startswith("Python код - ")]
        if not code_dirs:
            continue
        for code_dir in code_dirs:
            zip_name = f"{func_dir.name}.zip"
            zip_path = zip_dir / zip_name

            print(f"  {func_dir.name}...", end=" ")
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                work_dir = temp_path / "cloud_function"
                work_dir.mkdir()
                process_directory(code_dir, work_dir)
                copy_additions(addons_dir, work_dir)
                copy_addon_folders(addon_configs, work_dir)
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
