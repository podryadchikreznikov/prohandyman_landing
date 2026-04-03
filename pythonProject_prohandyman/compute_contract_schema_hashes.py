#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INITIAL_DIR = str((WORKSPACE_ROOT / "obsidian_prohandyman" / "𝒇 Функции").resolve())
EXCLUDED_TOP_LEVEL_DIRS = {"С ДРУГОГО ПРОЕКТА"}


def _is_excluded_path(path: Path) -> bool:
    return any(part in EXCLUDED_TOP_LEVEL_DIRS for part in path.parts)


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


def canonical_schema_bytes(schema_obj: object) -> bytes:
    txt = json.dumps(schema_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return txt.encode("utf-8")


def schema_sha256_hex(schema_obj: object) -> str:
    return hashlib.sha256(canonical_schema_bytes(schema_obj)).hexdigest()


def build_hashes_for_contract(contract: dict) -> dict:
    endpoints = contract.get("endpoints")
    req_schema = contract.get("request_schema")
    res_schema = contract.get("response_schema")
    schema_hash_alg = "sha256(json.dumps(schema, sort_keys=True, separators=(',',':'), ensure_ascii=False))"

    if isinstance(endpoints, dict):
        out_endpoints: dict = {}
        for path, spec in endpoints.items():
            if not isinstance(spec, dict):
                continue
            method = spec.get("method")
            endpoint_req_schema = spec.get("request_schema")
            endpoint_res_schema = spec.get("response_schema")
            if endpoint_req_schema is None or endpoint_res_schema is None:
                continue

            out_endpoints[path] = {
                "method": method,
                "request_schema_hash": schema_sha256_hex(endpoint_req_schema),
                "response_schema_hash": schema_sha256_hex(endpoint_res_schema),
            }

        return {
            "title": contract.get("title"),
            "schema_hash_alg": schema_hash_alg,
            "endpoints": out_endpoints,
        }

    if req_schema is None or res_schema is None:
        raise ValueError("contract must contain either endpoints or request_schema/response_schema")

    request_schema_hash = schema_sha256_hex(req_schema)
    response_schema_hash = schema_sha256_hex(res_schema)

    existing_request_hash = contract.get("request_schema_hash")
    existing_response_hash = contract.get("response_schema_hash")
    if existing_request_hash and str(existing_request_hash) != request_schema_hash:
        raise ValueError(
            f"request_schema_hash mismatch: expected {request_schema_hash}, got {existing_request_hash}"
        )
    if existing_response_hash and str(existing_response_hash) != response_schema_hash:
        raise ValueError(
            f"response_schema_hash mismatch: expected {response_schema_hash}, got {existing_response_hash}"
        )

    return {
        "title": contract.get("title"),
        "schema_hash_alg": schema_hash_alg,
        "request_schema_hash": request_schema_hash,
        "response_schema_hash": response_schema_hash,
    }


def collect_schema_hashes_super(functions_root: Path) -> dict:
    out = {
        "schema_hash_alg": "sha256(json.dumps(schema, sort_keys=True, separators=(',',':'), ensure_ascii=False))",
        "functions_root": str(functions_root),
        "functions": {},
    }

    for p in sorted(functions_root.rglob("schema_hashes.json")):
        if _is_excluded_path(p):
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            title = data.get("title")
            endpoints = data.get("endpoints")
            request_schema_hash = data.get("request_schema_hash")
            response_schema_hash = data.get("response_schema_hash")
            if not isinstance(endpoints, dict) and request_schema_hash is None and response_schema_hash is None:
                continue

            fn_dir = p.parent
            fn_name = fn_dir.name

            fn_entry = {
                "title": title,
                "schema_hashes_path": str(p),
            }
            if isinstance(endpoints, dict):
                fn_entry["endpoints"] = endpoints
            if request_schema_hash is not None:
                fn_entry["request_schema_hash"] = request_schema_hash
            if response_schema_hash is not None:
                fn_entry["response_schema_hash"] = response_schema_hash

            out["functions"][fn_name] = fn_entry
        except Exception:
            continue

    return out


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


def main() -> None:
    args = parse_args()
    base_path = resolve_base_path(args)
    if base_path is None:
        return

    print("\nШаг 2: Проверка legacy markdown внутри 'Python код - ...'...")
    legacy_md_contracts = sorted(base_path.rglob("contracts.json - *.md"))
    if legacy_md_contracts:
        print("[FAIL] Найдены legacy markdown-контракты. Сначала выполни миграцию:")
        for md_path in legacy_md_contracts:
            print(f"  - {md_path}")
        return

    print("\nШаг 3: Поиск contracts.json...")
    contracts = sorted(
        path
        for path in base_path.rglob("contracts.json")
        if any(part.startswith("Python код - ") for part in path.parts)
        and not _is_excluded_path(path)
    )
    if not contracts:
        print("[FAIL] contracts.json не найдены")
        return

    print("\nШаг 4: Генерация schema_hashes.json...")
    ok = 0
    fail = 0

    for contract_path in contracts:
        try:
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            hashes = build_hashes_for_contract(contract)

            out_path = contract_path.parent / "schema_hashes.json"
            out_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")

            print(f"  [OK] {out_path}")
            ok += 1
        except Exception as e:
            print(f"  [FAIL] {contract_path}: {e}")
            fail += 1

    print("\nГотово")
    print(f"  OK: {ok}")
    print(f"  FAIL: {fail}")

    out = collect_schema_hashes_super(base_path)
    out_path = Path(__file__).with_name("schema_hashes_super.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Wrote: {out_path}")
    print(f"     Functions: {len(out.get('functions') or {})}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[FAIL] Отменено")
