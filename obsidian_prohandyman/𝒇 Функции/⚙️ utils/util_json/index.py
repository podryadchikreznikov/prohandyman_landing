from __future__ import annotations
from typing import Any, Union
import json

def loads_safe(s: Union[str, bytes, None], default: Any = None, *, max_bytes: int = 2_000_000) -> Any:
    if s is None: return default
    if isinstance(s, bytes):
        if len(s) > max_bytes: return default
        s = s.decode("utf-8", errors="replace")
    else:
        if len(s.encode("utf-8")) > max_bytes: return default
    try: return json.loads(s)
    except Exception: return default

def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def is_json_like(text: str) -> bool:
    if not isinstance(text, str): return False
    t = text.lstrip(); return t.startswith("{") or t.startswith("[")