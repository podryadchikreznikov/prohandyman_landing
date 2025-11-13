from __future__ import annotations
import json, time, socket, ipaddress
from typing import Any, Dict, Optional, Iterable, List
from urllib.parse import urlparse
import requests

_REDACT = {"authorization","x-forwarded-authorization","proxy-authorization","cookie","set-cookie","x-api-key"}

def _canon(h: Dict[str, str]) -> Dict[str, str]: return {(k or "").lower(): v for k, v in (h or {}).items()}
def _redact(h: Dict[str, str]) -> Dict[str, str]: return {k: ("<redacted>" if k in _REDACT else v) for k, v in h.items()}
def _allowed(url: str, allow_hosts: Optional[Iterable[str]]) -> bool:
    if not allow_hosts: return True
    host = urlparse(url).hostname or ""; return any(host == a or host.endswith(f".{a}") for a in allow_hosts)

def _resolve_public(host: str) -> bool:
    try: infos = socket.getaddrinfo(host, None)
    except socket.gaierror: return False
    for fam,*_,sockaddr in infos:
        ip = sockaddr[0]
        try: ip_obj = ipaddress.ip_address(ip)
        except ValueError: return False
        if any((ip_obj.is_private, ip_obj.is_loopback, ip_obj.is_link_local, ip_obj.is_multicast, ip_obj.is_reserved)):
            return False
    return True

def invoke_function(
    target: str,
    *,
    method: str = "POST",
    json_payload: Any = None,
    data_bytes: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    # производительность: принесите готовые заголовки аутентификации (например, метадата/IAM) один раз
    auth_headers: Optional[Dict[str, str]] = None,
    forward_bearer: Optional[str] = None,
    forward_headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 20,
    retries: int = 2,
    backoff_base_s: float = 0.5,
    allow_hosts: Optional[Iterable[str]] = None,
    parse_json: bool = True,
    max_json_bytes: int = 2_000_000,
    verify_ssl: bool = True,
    block_private_networks: bool = True,
) -> Dict[str, Any]:
    p = urlparse(target)
    if p.scheme not in ("http","https"):
        return {"ok": False, "status_code": None, "headers": {}, "body_text": None, "json": None, "meta": {"elapsed_ms": 0, "attempts": 1, "target": target, "request_id": None}, "error": {"type":"invalid_target","message":"Unsupported URL scheme","retryable": False}}
    if not _allowed(target, allow_hosts):
        return {"ok": False, "status_code": None, "headers": {}, "body_text": None, "json": None, "meta": {"elapsed_ms": 0, "attempts": 1, "target": target, "request_id": None}, "error": {"type":"forbidden_host","message":"Host not allowed","retryable": False}}
    if block_private_networks and not _resolve_public(p.hostname or ""):
        return {"ok": False, "status_code": None, "headers": {}, "body_text": None, "json": None, "meta": {"elapsed_ms": 0, "attempts": 1, "target": target, "request_id": None}, "error": {"type":"blocked_host","message":"Target resolves to private/loopback/reserved IP","retryable": False}}

    req_headers = _canon(headers or {})
    if json_payload is not None and "content-type" not in req_headers:
        req_headers["content-type"] = "application/json"
    # готовые заголовки аутентификации (IAM/JWT) — без лишних запросов
    if auth_headers:
        for k, v in _canon(auth_headers).items():
            req_headers.setdefault(k, v)
    if forward_bearer and "authorization" not in req_headers:
        req_headers["authorization"] = f"Bearer {forward_bearer}"
    if forward_headers:
        for k, v in _canon(forward_headers).items():
            req_headers.setdefault(k, v)

    data = json.dumps(json_payload, ensure_ascii=False).encode("utf-8") if json_payload is not None else data_bytes
    started = time.perf_counter(); attempts = 0; last_exc = None

    for attempt in range(retries + 1):
        attempts = attempt + 1
        try:
            resp = requests.request(method.upper(), target, data=data, headers=req_headers, timeout=timeout_s, verify=verify_ssl)
            body_text = resp.text if resp.content is not None else None
            resp_h = _canon(dict(resp.headers))
            req_id = resp_h.get("x-request-id") or resp_h.get("request-id") or resp_h.get("traceparent")

            parsed = None
            if parse_json and body_text and len(resp.content) <= max_json_bytes:
                ct = resp_h.get("content-type","")
                if "json" in ct or body_text.lstrip().startswith(("{","[")):
                    try: parsed = resp.json()
                    except ValueError: parsed = None

            return {"ok": 200 <= resp.status_code < 300,
                    "status_code": resp.status_code,
                    "headers": resp_h,
                    "body_text": body_text,
                    "json": parsed,
                    "meta": {"elapsed_ms": int((time.perf_counter()-started)*1000), "attempts": attempts, "target": target, "request_id": req_id},
                    "error": None if 200 <= resp.status_code < 300 else {"type":"http_error","message": f"HTTP {resp.status_code}", "retryable": resp.status_code in (408,425,429,500,502,503,504), "details": {"resp_headers": _redact(resp_h), "snippet": body_text[:500] if body_text else None}}}
        except (requests.Timeout, requests.ConnectionError, socket.gaierror) as e:
            last_exc = e
            if attempt < retries: time.sleep(backoff_base_s * (2 ** attempt)); continue
            break
        except Exception as e:
            return {"ok": False, "status_code": None, "headers": {}, "body_text": None, "json": None, "meta": {"elapsed_ms": int((time.perf_counter()-started)*1000), "attempts": attempts or 1, "target": target, "request_id": None}, "error": {"type":"unexpected_error","message": str(e), "retryable": False}}
    return {"ok": False, "status_code": None, "headers": {}, "body_text": None, "json": None, "meta": {"elapsed_ms": int((time.perf_counter()-started)*1000), "attempts": attempts or 1, "target": target, "request_id": None}, "error": {"type":"network_error","message": str(last_exc) if last_exc else "network error", "retryable": True}}

# опционально: батч без повторной подготовки заголовков
def invoke_many(calls: List[Dict[str, Any]], *, common_auth_headers: Optional[Dict[str,str]] = None, **common_kw) -> List[Dict[str, Any]]:
    """
    calls: [{ "target": "...", "method": "POST", "json_payload": {...}, "headers": {...}, ... }, ...]
    common_auth_headers: пробрасываются во все вызовы (например, уже полученный IAM/JWT)
    common_kw: общие параметры (timeouts, retries, allow_hosts, ...)
    """
    out = []
    for c in calls:
        out.append(invoke_function(auth_headers=common_auth_headers, **{**common_kw, **c}))
    return out