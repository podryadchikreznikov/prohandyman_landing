# util_http/cors.py
from typing import Dict, Optional

def cors_headers(allow_origin: str = "*", allow_headers: str = "Content-Type,Authorization,X-Correlation-Id", allow_methods: str = "GET,POST,OPTIONS", allow_credentials: bool = False) -> Dict[str, str]:
    h = {"Access-Control-Allow-Origin": allow_origin, "Access-Control-Allow-Headers": allow_headers, "Access-Control-Allow-Methods": allow_methods}
    if allow_credentials: h["Access-Control-Allow-Credentials"] = "true"
    return h

def handle_preflight(event_headers: Dict[str,str], allow_origin: str = "*", allow_credentials: bool = False) -> Optional[Dict]:
    hdrs = {(k or "").lower(): v for k, v in (event_headers or {}).items()}
    if "origin" in hdrs and "access-control-request-method" in hdrs:
        return {"statusCode": 204, "headers": cors_headers(allow_origin, allow_credentials=allow_credentials), "body": ""}
    return None