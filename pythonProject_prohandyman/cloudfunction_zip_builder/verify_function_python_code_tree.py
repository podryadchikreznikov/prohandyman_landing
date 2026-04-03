#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_INITIAL_DIR = str(
    (Path(__file__).resolve().parents[2] / "obsidian_prohandyman" / "𝒇 Функции").resolve()
)
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


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
    parser.add_argument(
        "--strict-head-compare",
        action="store_true",
        help="Сравнивать текущее содержимое с legacy markdown-исходниками из HEAD",
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


def iter_python_code_dirs(base_path: Path):
    for path in sorted(base_path.rglob("*")):
        if path.is_dir() and path.name.startswith("Python код - "):
            yield path


def git_show_head_text(rel_path: Path) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"HEAD:{rel_path.as_posix()}"],
        cwd=WORKSPACE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def collect_head_legacy_md(base_path: Path) -> list[Path]:
    base_rel = str(base_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=false", "diff", "--name-only", "--diff-filter=D", "HEAD"],
        cwd=WORKSPACE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        check=True,
    )
    result: list[Path] = []
    for line in proc.stdout.splitlines():
        clean = line.strip().strip('"')
        if not clean.startswith(base_rel):
            continue
        rel = Path(clean)
        if "Python код - " not in rel.as_posix():
            continue
        if rel.suffix.lower() != ".md":
            continue
        if " - " not in rel.stem:
            continue
        result.append(rel)
    return result


def main() -> None:
    args = parse_args()
    base_path = resolve_base_path(args)
    if base_path is None:
        return

    print("\nШаг 2: Базовая валидация дерева 'Python код - ...'...")
    code_dirs = list(iter_python_code_dirs(base_path))
    if not code_dirs:
        print("[FAIL] Папки 'Python код - ...' не найдены")
        sys.exit(1)

    md_left: list[str] = []
    fence_hits: list[str] = []
    compile_failures: list[str] = []
    json_failures: list[str] = []
    py_ok = 0
    json_ok = 0
    file_count = 0

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        compile_index = 0

        for code_dir in code_dirs:
            for path in sorted(code_dir.rglob("*")):
                if "__pycache__" in path.parts:
                    continue
                if not path.is_file():
                    continue
                file_count += 1
                rel = path.relative_to(WORKSPACE_ROOT)
                if path.suffix.lower() == ".md":
                    md_left.append(str(rel))
                text = path.read_text(encoding="utf-8")
                if "```" in text:
                    fence_hits.append(str(rel))
                if path.suffix == ".py":
                    try:
                        compile_index += 1
                        cfile = temp_root / f"{compile_index}.pyc"
                        py_compile.compile(str(path), cfile=str(cfile), doraise=True)
                        py_ok += 1
                    except Exception as exc:
                        compile_failures.append(f"{rel}: {exc}")
                elif path.suffix == ".json":
                    try:
                        json.loads(text)
                        json_ok += 1
                    except Exception as exc:
                        json_failures.append(f"{rel}: {exc}")

    print(f"[OK] Папок кода: {len(code_dirs)}")
    print(f"[OK] Файлов проверено: {file_count}")
    print(f"[OK] Python скомпилировано: {py_ok}")
    print(f"[OK] JSON распарсено: {json_ok}")

    if md_left:
        print("[FAIL] Остались markdown-файлы внутри 'Python код - ...':")
        for item in md_left:
            print(f"  - {item}")
    if fence_hits:
        print("[FAIL] Найдены fenced-блоки внутри реальных исходников:")
        for item in fence_hits[:50]:
            print(f"  - {item}")
    if compile_failures:
        print("[FAIL] Есть ошибки компиляции Python:")
        for item in compile_failures[:50]:
            print(f"  - {item}")
    if json_failures:
        print("[FAIL] Есть ошибки JSON:")
        for item in json_failures[:50]:
            print(f"  - {item}")

    compare_failures: list[str] = []
    missing_targets: list[str] = []
    missing_legacy_sources: list[str] = []

    if args.strict_head_compare:
        print("\nШаг 3: Сверка с legacy markdown-исходниками из HEAD...")
        legacy_md_paths = collect_head_legacy_md(base_path)
        for rel in legacy_md_paths:
            target_name = re.split(r"\s-\s", rel.stem, maxsplit=1)[0]
            target_rel = rel.with_name(target_name)
            target_path = WORKSPACE_ROOT / target_rel
            md_text = git_show_head_text(rel)
            if md_text is None:
                missing_legacy_sources.append(str(rel))
                continue
            expected = extract_source_from_markdown(md_text).rstrip("\n")
            if not target_path.exists():
                if expected:
                    missing_targets.append(f"{rel} -> {target_rel}")
                continue
            actual = target_path.read_text(encoding="utf-8").rstrip("\n")
            if actual != expected:
                compare_failures.append(f"{target_rel} != extracted({rel})")

        print(f"[OK] Legacy markdown в HEAD: {len(legacy_md_paths)}")

        if missing_targets:
            print("[FAIL] Для части legacy md не найден новый target:")
            for item in missing_targets[:50]:
                print(f"  - {item}")
        if compare_failures:
            print("[FAIL] Есть несовпадения содержимого после миграции:")
            for item in compare_failures[:50]:
                print(f"  - {item}")
        if missing_legacy_sources:
            print("[FAIL] Не удалось прочитать legacy md из HEAD:")
            for item in missing_legacy_sources[:50]:
                print(f"  - {item}")

    has_failures = any(
        [
            md_left,
            fence_hits,
            compile_failures,
            json_failures,
            compare_failures,
            missing_targets,
            missing_legacy_sources,
        ]
    )
    if has_failures:
        sys.exit(1)

    print("\nГотово")
    print("[OK] Дерево 'Python код - ...' выглядит консистентно")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[FAIL] Отменено")
        sys.exit(130)
