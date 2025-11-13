# util_http/response.py
import json
from typing import Any, Dict, Optional
JSON_CT = "application/json; charset=utf-8"

def json_response(code: int, payload: Any, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    return {"statusCode": code, "headers": {"Content-Type": JSON_CT, **(headers or {})}, "body": json.dumps(payload, ensure_ascii=False, default=str)}

ok          = lambda data=None, **kw: json_response(200, data if data is not None else {"message":"OK"}, **kw)
created     = lambda data=None, **kw: json_response(201, data if data is not None else {"message":"Created"}, **kw)
bad_request = lambda msg="Bad Request", **kw: json_response(400, {"error":{"code":"bad_request","message":msg}}, **kw)
unauthorized= lambda msg="Unauthorized", **kw: json_response(401, {"error":{"code":"unauthorized","message":msg}}, **kw)
forbidden   = lambda msg="Forbidden", **kw: json_response(403, {"error":{"code":"forbidden","message":msg}}, **kw)
not_found   = lambda msg="Not Found", **kw: json_response(404, {"error":{"code":"not_found","message":msg}}, **kw)
conflict    = lambda msg="Conflict", **kw: json_response(409, {"error":{"code":"conflict","message":msg}}, **kw)
too_many    = lambda msg="Too Many Requests", **kw: json_response(429, {"error":{"code":"rate_limited","message":msg}}, **kw)
server_error= lambda msg="Internal Server Error", **kw: json_response(500, {"error":{"code":"internal","message":msg}}, **kw)