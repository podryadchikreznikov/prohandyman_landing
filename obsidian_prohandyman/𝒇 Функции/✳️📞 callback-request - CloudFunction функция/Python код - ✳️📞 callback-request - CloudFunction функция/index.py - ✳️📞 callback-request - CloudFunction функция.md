```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import re
import traceback
from typing import Any, Dict, Optional

import requests

from utils.util_log.logger import JsonLogger
from utils.util_http.cors import cors_headers, handle_preflight
from utils.util_http.request import parse_event, EventParseError
from utils.util_http.response import ok, bad_request, server_error
from utils.util_errors.exceptions import Internal
from utils.util_errors.to_response import app_error_to_http
from utils.util_sms.sms_sender import validate_phone_number

logger = JsonLogger()

BASE_HEADERS = {
    **cors_headers(allow_origin=os.getenv("CORS_ALLOW_ORIGIN", "*")),
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _with_base_headers(resp: Dict[str, Any]) -> Dict[str, Any]:
    headers = resp.get("headers") or {}
    resp["headers"] = {**BASE_HEADERS, **headers}
    return resp


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        logger.error("config.env_missing", env=name)
        raise Internal("Service configuration error")
    return v


def _build_message(
    user_name: Optional[str],
    comment: Optional[str],
    email: Optional[str],
    phone_e164: Optional[str],
) -> str:
    parts = ["Оставлена заявка на обратный звонок."]
    if user_name:
        parts.append(f"Имя: {user_name}")
    if comment:
        parts.append(f"Комментарий: {comment}")
    if email:
        parts.append(f"Email: {email}")
    if phone_e164:
        parts.append(f"Телефон: +{phone_e164}")
    return "\n".join(parts)


# Официальные коды ошибок SMSЦЕНТР (1–9)
# https://smsc.ru / документация (или их зеркала)
SMSC_ERROR_DESCRIPTIONS: Dict[int, str] = {
    1: "Ошибка в параметрах.",
    2: (
        "Неверный логин или пароль, либо отправка с IP-адреса, "
        "не входящего в список разрешённых."
    ),
    3: "Недостаточно средств на счёте клиента.",
    4: "IP-адрес временно заблокирован из-за частых ошибок в запросах.",
    5: "Неверный формат даты.",
    6: (
        "Сообщение запрещено (по тексту или по имени отправителя), "
        "либо массовые/рекламные сообщения без договора."
    ),
    7: "Неверный формат номера телефона.",
    8: "Сообщение на указанный номер не может быть доставлено.",
    9: (
        "Слишком много одинаковых запросов или слишком много "
        "одновременных запросов (too many concurrent requests)."
    ),
}


class SMSCError(Exception):
    """Логическая ошибка на стороне SMSC (правильный HTTP, но ошибка в ответе)."""

    def __init__(self, message: str, code: Optional[int] = None, technical_desc: Optional[str] = None):
        super().__init__(message)
        self.code = code
        self.technical_desc = technical_desc


def _normalize_error_code(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_smsc_error_message(code: Optional[int], desc: Optional[str]) -> str:
    # Человекочитаемое сообщение на основе официального списка и текстового описания
    parts = []
    if code is not None:
        parts.append(f"код {code}")
    human = SMSC_ERROR_DESCRIPTIONS.get(code) if code is not None else None
    if human:
        parts.append(human.rstrip("."))
    if desc and (not human or desc.strip() not in human):
        parts.append(desc.strip())
    if not parts:
        return "Неизвестная ошибка SMSC."
    # Склеиваем, гарантируя точку в конце
    msg = ": ".join([parts[0], " ".join(parts[1:])]) if len(parts) > 1 else parts[0]
    if not msg.endswith("."):
        msg += "."
    return msg


def _parse_plain_error_body(body: str) -> Optional[SMSCError]:
    """
    Пытается распарсить текстовый ответ вида:
    'ERROR = N (описание)' или 'ERROR=N (описание)'.
    Если удаётся — возвращает SMSCError, иначе None.
    """
    text = (body or "").strip()
    if not text:
        return None

    # Простейший вариант: начинается с ERROR
    if not text.upper().startswith("ERROR"):
        return None

    code_match = re.search(r"ERROR\s*=?\s*(\d+)", text, flags=re.IGNORECASE)
    code = _normalize_error_code(code_match.group(1)) if code_match else None

    # Пытаемся вытащить описание из скобок
    desc_match = re.search(r"\((.*?)\)", text)
    desc = desc_match.group(1).strip() if desc_match else None

    message = _build_smsc_error_message(code, desc or text)
    return SMSCError(message=message, code=code, technical_desc=text)


def _check_smsc_json_payload(payload: Dict[str, Any]) -> None:
    """
    Проверяет JSON-ответ от SMSC.

    Ожидаемый формат при fmt=3:
    - при успехе: {"id": <id>, "cnt": <n>, ...}
    - при ошибке: {"error_code": N, "error": "описание", ...}

    При наличии признаков ошибки выбрасывает SMSCError.
    """
    if not isinstance(payload, dict):
        raise SMSCError("Некорректный формат ответа от SMSC.", technical_desc=repr(payload))

    # Верхнеуровневая ошибка (официальный формат: error_code + error)
    error_code = _normalize_error_code(payload.get("error_code"))
    error_desc = payload.get("error") or payload.get("error_description")

    if error_code is not None or error_desc:
        message = _build_smsc_error_message(error_code, error_desc)
        raise SMSCError(message=message, code=error_code, technical_desc=error_desc or json.dumps(payload, ensure_ascii=False))

    # Дополнительная проверка массива phones при op=1:
    phones = payload.get("phones")
    if isinstance(phones, list):
        for phone_entry in phones:
            if not isinstance(phone_entry, dict):
                continue
            status = str(phone_entry.get("status", "")).strip()
            per_phone_error = phone_entry.get("error")
            # Согласно документации, статус 0/1 — ОК, остальное трактуем как ошибку.
            if per_phone_error and status not in ("0", "1"):
                # Часто per_phone_error уже текстовый вид ошибки; кода может не быть.
                message = _build_smsc_error_message(error_code=None, desc=str(per_phone_error))
                raise SMSCError(
                    message=message,
                    code=None,
                    technical_desc=json.dumps(phone_entry, ensure_ascii=False),
                )

    # Если ошибок не видно, считаем ответ валидным успехом.


def _send_sms_to_manager(manager_phone_e164: str, text: str) -> None:
    """Отправляет SMS руководителю через SMSC.ru напрямую (без utils-расширений)."""
    login = os.getenv("SMSC_LOGIN")
    password = os.getenv("SMSC_PASSWORD")
    if not login or not password:
        logger.error("smsc.creds_missing")
        raise RuntimeError("SMSC credentials missing")

    params = {
        "login": login,
        "psw": password,
        "phones": manager_phone_e164,
        "mes": text,
        "fmt": 3,  # JSON-ответ
        "charset": "utf-8",
    }

    # Не логируем пароль в открытом виде
    safe_params = dict(params)
    if "psw" in safe_params:
        safe_params["psw"] = "***"

    try:
        resp = requests.get("https://smsc.ru/sys/send.php", params=params, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error(
            "smsc.request_error",
            error=str(e),
            trace=traceback.format_exc(),
            response_text=getattr(e, "response", None).text if getattr(e, "response", None) is not None else None,
            status_code=getattr(getattr(e, "response", None), "status_code", None),
            params=safe_params,
        )
        raise RuntimeError("SMSC request error")

    # Пытаемся распарсить JSON, при неудаче — разбираем текстовый ERROR = N (...)
    try:
        payload = resp.json()
    except ValueError:
        body = (resp.text or "").strip()
        logger.error(
            "smsc.invalid_json",
            body=body,
            status_code=resp.status_code,
            trace=traceback.format_exc(),
            params=safe_params,
        )
        parsed_error = _parse_plain_error_body(body)
        if parsed_error:
            # Это легальная ошибка SMSC с понятным кодом
            raise parsed_error
        raise RuntimeError("SMSC invalid JSON response")

    # На этом этапе JSON корректен — валидируем логическую часть (error_code, phones[] и т.д.)
    try:
        _check_smsc_json_payload(payload)
    except SMSCError as e:
        logger.error(
            "smsc.api_error",
            error=str(e),
            code=e.code,
            technical_desc=e.technical_desc,
            payload=payload,
            params=safe_params,
        )
        raise

    # Успешный ответ — логируем для отладки (без чувствительных данных)
    logger.info(
        "smsc.sent",
        smsc_payload=payload,
        params=safe_params,
    )


def handler(event, context):  # noqa: D401
    logger.info("callback_request.invoked")

    # CORS preflight
    pre = handle_preflight((event or {}).get("headers") or {}, allow_origin=os.getenv("CORS_ALLOW_ORIGIN", "*"))
    if pre:
        return _with_base_headers(pre)

    # Parse request
    try:
        req = parse_event(event)
        body = req.get("body_dict") or {}
    except EventParseError as e:
        logger.warn("callback_request.parse_error", error=str(e), trace=traceback.format_exc())
        return _with_base_headers(bad_request(f"Invalid request: {e}"))

    logger.info(
        "callback_request.received",
        headers=logger.redact_headers((event or {}).get("headers") or {}),
        payload=body,
    )

    email = (body.get("email") or "").strip().lower() if body.get("email") else None
    phone_raw = (body.get("phone_number") or "").strip() if body.get("phone_number") else None
    user_name = (body.get("user_name") or "").strip() or None
    comment = (body.get("comment") or "").strip() or None

    phone_e164 = validate_phone_number(phone_raw) if phone_raw else None
    if phone_raw and not phone_e164:
        logger.warn("callback_request.invalid_phone", phone=phone_raw)
        return _with_base_headers(bad_request("Invalid phone number format."))

    if not email and not phone_e164:
        logger.warn("callback_request.missing_identifier")
        return _with_base_headers(bad_request("Either email or phone_number is required."))

    # Compose message
    message_text = _build_message(user_name, comment, email, phone_e164)

    # Resolve manager/operator phone from env and send SMS
    try:
        manager_phone_raw = _require_env("CALLBACK_NOTIFY_PHONE")
        manager_phone = validate_phone_number(manager_phone_raw)
        if not manager_phone:
            logger.error("callback_request.invalid_manager_phone", value=manager_phone_raw)
            return _with_base_headers(server_error("Service configuration error: invalid manager phone"))

        _send_sms_to_manager(manager_phone, message_text)

    except SMSCError as e:
        # Чёткое сообщение, что именно не понравилось SMSC
        logger.error(
            "callback_request.smsc_error",
            error=str(e),
            code=e.code,
            technical_desc=e.technical_desc,
            trace=traceback.format_exc(),
            payload=message_text,
        )
        user_msg = "SMSC error"
        if e.code is not None:
            user_msg += f" (code {e.code})"
        user_msg += f": {e}"
        return _with_base_headers(server_error(user_msg))

    except Exception as e:  # прочие ошибки (сеть, инфраструктура и т.п.)
        logger.error(
            "callback_request.send_failed",
            error=str(e),
            trace=traceback.format_exc(),
            payload=message_text,
        )
        return _with_base_headers(server_error("Failed to send SMS"))

    logger.info("callback_request.sent", manager_phone=manager_phone, lead_phone=phone_e164, email=email)
    return _with_base_headers(ok({"message": "Callback request sent via SMS."}))
```