#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import re
from pathlib import Path

DEFAULT_INITIAL_DIR = str(
    (Path(__file__).resolve().parents[2] / "obsidian_prohandyman" / "𝒇 Функции").resolve()
)


def select_folder() -> str:
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder_path = filedialog.askdirectory(
        title="Выберите папку с функциями ('𝒇 Функции')",
        initialdir=DEFAULT_INITIAL_DIR,
    )
    root.destroy()
    return folder_path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--functions-root", help="Путь к папке с функциями")
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Не открывать проводник; использовать только --functions-root",
    )
    return parser.parse_args()


def resolve_base_path(args) -> Path | None:
    if args.functions_root:
        base_path = Path(args.functions_root).expanduser().resolve()
        print(f"\nШаг 1: Базовая папка... [OK] {base_path}")
        return base_path

    if args.no_ui:
        print("\nШаг 1: Базовая папка... [FAIL] В режиме --no-ui нужно обязательно передать --functions-root")
        return None

    print("\nШаг 1: Выбор папки...", end=" ")
    base_folder = select_folder()
    if not base_folder:
        print("[FAIL] Папка не выбрана")
        return None

    base_path = Path(base_folder)
    if not base_path.exists():
        print(f"[FAIL] Папка не существует: {base_folder}")
        return None
    print(f"[OK] {base_path.name}")
    return base_path


def iter_python_code_dirs(base_path: Path):
    for path in sorted(base_path.rglob("*")):
        if path.is_dir() and path.name.startswith("Python код - "):
            yield path


def normalize_target_name(md_path: Path) -> str:
    return re.split(r"\s-\s", md_path.stem, maxsplit=1)[0]


def extract_source_from_markdown(text: str) -> str:
    pattern = r"```python\n(.*?)\n```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        return "\n".join(matches)

    python_lines = []
    for line in text.split("\n"):
        if line.strip().startswith("```") or line.strip().startswith("#"):
            continue
        python_lines.append(line)
    return "\n".join(python_lines)


def migrate_markdown_file(md_path: Path) -> tuple[Path, bool]:
    target_name = normalize_target_name(md_path)
    if not target_name:
        raise RuntimeError(f"Не удалось вычислить target-имя для {md_path}")

    target_path = md_path.with_name(target_name)
    rendered = extract_source_from_markdown(md_path.read_text(encoding="utf-8"))

    if target_path.exists():
        existing = target_path.read_text(encoding="utf-8")
        if existing != rendered:
            raise RuntimeError(
                f"Конфликт миграции: target уже существует и отличается по содержимому: {target_path}"
            )
        md_path.unlink()
        return target_path, False

    target_path.write_text(rendered, encoding="utf-8")
    md_path.unlink()
    return target_path, True


def main() -> None:
    args = parse_args()
    base_path = resolve_base_path(args)
    if base_path is None:
        return

    print("\nШаг 2: Поиск markdown-исходников внутри 'Python код - ...'...")
    md_files: list[Path] = []
    for code_dir in iter_python_code_dirs(base_path):
        md_files.extend(sorted(code_dir.rglob("*.md")))

    if not md_files:
        print("[OK] Markdown-исходники не найдены")
        return

    print(f"[OK] Найдено файлов: {len(md_files)}")
    print("\nШаг 3: Миграция...")

    created = 0
    removed_legacy = 0

    for md_path in md_files:
        target_path, was_created = migrate_markdown_file(md_path)
        if was_created:
            created += 1
        else:
            removed_legacy += 1
        print(f"  [OK] {md_path} -> {target_path}")

    remaining: list[Path] = []
    for code_dir in iter_python_code_dirs(base_path):
        remaining.extend(sorted(code_dir.rglob("*.md")))

    if remaining:
        raise RuntimeError(
            "После миграции внутри 'Python код - ...' остались markdown-файлы:\n"
            + "\n".join(str(path) for path in remaining)
        )

    print("\nГотово")
    print(f"  Создано target-файлов: {created}")
    print(f"  Удалено legacy-md: {created + removed_legacy}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[FAIL] Отменено")
