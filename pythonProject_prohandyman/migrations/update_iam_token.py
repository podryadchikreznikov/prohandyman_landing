from __future__ import annotations

import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

ROOT = Path(__file__).resolve().parent
IAM_TOKEN_FILE = ROOT / "iam.token"
YC_TIMEOUT = 20


@dataclass
class RunResult:
    code: int
    out: str
    err: str


class CmdError(RuntimeError):
    pass


def which(bin_name: str) -> Optional[str]:
    from shutil import which as _which
    return _which(bin_name)


def run(cmd: Sequence[str], timeout: int) -> RunResult:
    printable = " ".join(shlex.quote(x) for x in cmd)
    print()
    print(f"$ {printable}")
    try:
        cp = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise CmdError(f"> Таймаут: {printable}") from e
    out, err = cp.stdout or "", cp.stderr or ""
    if cp.returncode != 0 and err.strip():
        print(err.rstrip())
    return RunResult(cp.returncode, out, err)


def main() -> None:
    if not which("yc"):
        raise CmdError(
            "> Не найден 'yc' в PATH. Установи Yandex Cloud CLI и выполни 'yc init'."
        )
    print("🔐 Обновляем IAM‑токен (yc iam create-token)…")
    rr = run(["yc", "iam", "create-token"], timeout=YC_TIMEOUT)
    if rr.code != 0 or not rr.out.strip():
        raise CmdError(
            "> Не удалось получить IAM‑токен (yc iam create-token)."
        )
    tok = rr.out.strip()
    IAM_TOKEN_FILE.write_text(tok, encoding="utf-8")
    print(f"✅ Токен обновлён: {IAM_TOKEN_FILE}")


if __name__ == "__main__":
    try:
        main()
    except CmdError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n> Отменено пользователем.")
        sys.exit(1)
