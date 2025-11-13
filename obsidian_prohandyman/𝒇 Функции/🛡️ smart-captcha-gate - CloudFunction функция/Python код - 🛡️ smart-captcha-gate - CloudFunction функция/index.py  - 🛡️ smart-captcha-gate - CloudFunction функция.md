```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import traceback
from typing import Any, Dict, Optional

import requests

from utils.util_log.logger import JsonLogger
from utils.util_json.index import loads_safe


logger = JsonLogger()


def _get_header_ci(headers: dict, name: str) -> Optional[str]:
    if not headers:
        return None
    lname = name.lower()
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == lname:
            return v
    return None


def _get_client_ip(event: Dict[str, Any]) -> Optional[str]:
    rc = event.get("requestContext") or {}
    ident = rc.get("identity") or {}
    ip = ident.get("sourceIp")
    if ip:
        return ip
    http = rc.get("http") or {}
    return http.get("sourceIp")


def _verify_smartcaptcha(token: str, client_ip: Optional[str]) -> bool:
    secret = os.getenv("SMARTCAPTCHA_SERVER_KEY")
    if not secret:
        logger.error("captcha.secret_missing")
        return False
    params = {"secret": secret, "token": token}
    if client_ip:
        params["ip"] = client_ip
    try:
        r = requests.get("https://smartcaptcha.yandexcloud.net/validate", params=params, timeout=5)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        logger.error(
            "captcha.request_error",
            error=str(e),
            trace=traceback.format_exc(),
            params=params,
            response=getattr(e, "response", None),
        )
        return False
    except ValueError:
        logger.error("captcha.invalid_json", trace=traceback.format_exc())
        return False
    else:
        logger.info("captcha.validation_response", data=data, params=params)
    return isinstance(data, dict) and data.get("status") == "ok"


def handler(event, context):
    logger.info("smart_captcha_gate.invoked")
    try:
        headers = (event.get("headers") or {}) or {}
    except Exception:
        headers = {}

    logger.info(
        "smart_captcha_gate.request",
        headers=logger.redact_headers(headers),
        method=(
            (event.get("requestContext") or {}).get("http", {}) or {}
        ).get("method")
        or event.get("httpMethod"),
    )

    # 1) Извлечение токена из заголовка или тела
    token = _get_header_ci(headers, "SmartCaptcha-Token") or _get_header_ci(headers, "X-Captcha-Token")
    token_preview = f"{token[:8]}..." if token else None

    if not token:
        body_raw = event.get("body")
        body_dict: Dict[str, Any] = {}
        if isinstance(body_raw, str) and body_raw.strip().startswith(('{','[')):
            try:
                body_dict = json.loads(body_raw)
            except Exception:
                body_dict = {}
        elif isinstance(body_raw, (bytes, bytearray)):
            try:
                body_dict = json.loads(body_raw.decode('utf-8', errors='replace'))
            except Exception:
                body_dict = {}
        token = (body_dict.get("captcha_token") or "").strip() if isinstance(body_dict, dict) else None

    if not token:
        logger.warn("smart_captcha_gate.no_token", event=event)
        return {"isAuthorized": False}

    # 2) Верификация в SmartCaptcha
    ip = _get_client_ip(event)
    ok = _verify_smartcaptcha(token, ip)
    if not ok:
        logger.warn("smart_captcha_gate.failed", ip=ip, token_preview=token_preview)
        return {"isAuthorized": False}

    logger.info("smart_captcha_gate.success", ip=ip, token_preview=token_preview)

    # 3) Формируем ответ для API Gateway
    ctx = {"captcha": "ok"}
    return {"isAuthorized": True, "context": {"captcha_ctx": json.dumps(ctx, ensure_ascii=False)}}
```