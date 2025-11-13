# util_http/request.py
from __future__ import annotations
import json, base64
from typing import Any, Dict, Optional, TypedDict

class ParsedRequest(TypedDict, total=False):
    body_dict: Dict[str, Any]
    body_text: Optional[str]
    query: Dict[str, Any]
    headers: Dict[str, str]
    path_params: Dict[str, Any]
    action: Optional[str]
    bearer: Optional[str]

class EventParseError(ValueError): ...

def parse_event(event: Dict[str, Any], *, action_fields: tuple[str, ...] = ("action",), max_body_bytes: int = 1_000_000, assume_json: bool = True) -> ParsedRequest:
    headers = {(k or "").lower(): v for k, v in (event.get("headers") or {}).items()}
    query = event.get("queryStringParameters") or {}
    path_params = event.get("pathParameters") or {}

    body_raw = event.get("body")
    if body_raw and event.get("isBase64Encoded"):
        try: body_raw = base64.b64decode(body_raw)
        except Exception as e: raise EventParseError(f"Base64 decode error: {e}")

    if isinstance(body_raw, bytes):
        if len(body_raw) > max_body_bytes: raise EventParseError("Body too large")
        body_text = body_raw.decode("utf-8", errors="replace")
    elif isinstance(body_raw, str):
        if len(body_raw.encode("utf-8")) > max_body_bytes: raise EventParseError("Body too large")
        body_text = body_raw
    else:
        body_text = None

    body_dict: Dict[str, Any] = {}
    if assume_json and body_text and body_text.lstrip().startswith(("{","[")):
        try: body_dict = json.loads(body_text)
        except json.JSONDecodeError as e: raise EventParseError(f"Invalid JSON: {e}")

    gw = (event.get("requestContext") or {}).get("apiGateway") or {}
    op = gw.get("operationContext") or {}
    action = op.get("action")
    if not action:
        for f in action_fields:
            if f in body_dict: action = body_dict.get(f); break

    bearer = None
    for key in ("x-forwarded-authorization","authorization"):
        val = headers.get(key)
        if val and val.lower().startswith("bearer "):
            bearer = val.split(" ",1)[1]; break

    return {"body_dict": body_dict or {}, "body_text": body_text, "query": query, "headers": headers, "path_params": path_params, "action": action, "bearer": bearer}