from typing import Any, Optional, Dict, TypedDict

class ErrorInfo(TypedDict, total=False):
    type: str
    message: str
    retryable: bool
    details: Dict[str, Any]

class Result(TypedDict, total=False):
    ok: bool
    error: Optional[ErrorInfo]
    data: Any
    meta: Dict[str, Any]