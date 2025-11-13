import json, sys, uuid, time
from typing import Any, Dict, Optional

_DEFAULT_REDACTIONS = {"authorization","x-forwarded-authorization","proxy-authorization","cookie","set-cookie","x-api-key"}

def _redact(h: Dict[str, Any], redactions=_DEFAULT_REDACTIONS) -> Dict[str, Any]:
    return {k: ("<redacted>" if isinstance(v, str) and k.lower() in redactions else v) for k,v in (h or {}).items()}

class JsonLogger:
    def __init__(self, *, correlation_id: Optional[str] = None, redactions: Optional[set[str]] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.redactions = redactions or set(_DEFAULT_REDACTIONS)

    def log(self, level: str, msg: str, **fields: Any) -> None:
        rec = {"level": level.lower(), "msg": msg, "ts_ms": int(time.time()*1000), "correlation_id": self.correlation_id, **fields}
        try:
            sys.stdout.write(json.dumps(rec, ensure_ascii=False, default=str)+"\n"); sys.stdout.flush()
        except Exception:
            print({"level": level, "msg": msg, **fields})

    def info(self, msg: str, **fields: Any): self.log("INFO", msg, **fields)
    def warn(self, msg: str, **fields: Any): self.log("WARN", msg, **fields)
    def error(self, msg: str, **fields: Any): self.log("ERROR", msg, **fields)

    def redact_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        return _redact(headers, self.redactions)