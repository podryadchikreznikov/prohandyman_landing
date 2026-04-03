```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import html
import os
import smtplib
import ssl
import traceback
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any, Dict, Optional

from utils.util_log.logger import JsonLogger
from utils.util_http.cors import cors_headers, handle_preflight
from utils.util_http.request import parse_event, EventParseError
from utils.util_http.response import ok, bad_request, server_error, json_response
from utils.util_errors.exceptions import Internal
from utils.util_sms.sms_sender import validate_phone_number

logger = JsonLogger()
CONTRACTS_PATH = Path(__file__).with_name("contracts.json")
_CONTRACTS_CACHE: Optional[Dict[str, str]] = None
OUTDATED_CLIENT_SCHEMA_MESSAGE = "Client schema version mismatch. Please update your application."

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


def _get_header_ci(headers: Dict[str, Any], name: str) -> Optional[str]:
    if not headers:
        return None
    lname = name.lower()
    for key, value in headers.items():
        if isinstance(key, str) and key.lower() == lname:
            return value
    return None


def _normalize_email_address(address: str) -> str:
    cleaned = (address or "").strip()
    if not cleaned or "@" not in cleaned:
        return cleaned
    local_part, domain = cleaned.rsplit("@", 1)
    try:
        domain_ascii = domain.encode("idna").decode("ascii")
    except Exception:
        return cleaned
    return f"{local_part}@{domain_ascii}"


def _format_request_text(event: Dict[str, Any], req: Dict[str, Any]) -> str:
    http_ctx = ((event.get("requestContext") or {}).get("http") or {}) if event else {}
    snapshot = {
        "method": http_ctx.get("method") or (event or {}).get("httpMethod"),
        "path": http_ctx.get("path") or (event or {}).get("path"),
        "headers": logger.redact_headers((event or {}).get("headers") or {}),
        "query": req.get("query") or {},
        "path_params": req.get("path_params") or {},
        "action": req.get("action"),
        "body_text": req.get("body_text"),
        "body_dict": req.get("body_dict") or {},
        "isBase64Encoded": bool((event or {}).get("isBase64Encoded")),
        "requestContext": (event or {}).get("requestContext") or {},
    }
    return json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)


def _load_contracts() -> Dict[str, str]:
    global _CONTRACTS_CACHE
    if _CONTRACTS_CACHE is not None:
        return _CONTRACTS_CACHE

    try:
        raw = CONTRACTS_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        request_schema_hash = str(data["request_schema_hash"]).strip()
        response_schema_hash = str(data["response_schema_hash"]).strip()
        error_on_mismatch = data.get("error_on_mismatch") or {}
        mismatch_message = str(error_on_mismatch.get("message") or OUTDATED_CLIENT_SCHEMA_MESSAGE).strip()
    except Exception as exc:
        logger.error(
            "callback_request.contract_config_error",
            error=str(exc),
            trace=traceback.format_exc(),
            contract_file=str(CONTRACTS_PATH),
        )
        raise Internal("Service configuration error")

    if not request_schema_hash or not response_schema_hash:
        logger.error(
            "callback_request.contract_config_error",
            contract_file=str(CONTRACTS_PATH),
            error="Missing request_schema_hash/response_schema_hash",
        )
        raise Internal("Service configuration error")

    _CONTRACTS_CACHE = {
        "request_schema_hash": request_schema_hash,
        "response_schema_hash": response_schema_hash,
        "mismatch_message": mismatch_message or OUTDATED_CLIENT_SCHEMA_MESSAGE,
    }
    return _CONTRACTS_CACHE


def _contract_mismatch_response() -> Dict[str, Any]:
    contracts = _load_contracts()
    payload = {
        "error": {
            "code": "OUTDATED_CLIENT_SCHEMA",
            "message": contracts["mismatch_message"],
        }
    }
    return _with_base_headers(json_response(426, payload))


def _validate_contract_hashes(headers: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    contracts = _load_contracts()
    request_schema_hash = _get_header_ci(headers, "X-Request-Schema-Hash")
    response_schema_hash = _get_header_ci(headers, "X-Response-Schema-Hash")

    if request_schema_hash != contracts["request_schema_hash"] or response_schema_hash != contracts["response_schema_hash"]:
        logger.warn(
            "callback_request.contract_mismatch",
            request_schema_hash=request_schema_hash,
            response_schema_hash=response_schema_hash,
            expected_request_schema_hash=contracts["request_schema_hash"],
            expected_response_schema_hash=contracts["response_schema_hash"],
        )
        return _contract_mismatch_response()

    return None


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


def _build_html_message(
    user_name: Optional[str],
    comment: Optional[str],
    email: Optional[str],
    phone_e164: Optional[str],
) -> str:
    def _cell(value: Optional[str]) -> str:
        return html.escape(value or "—")

    rows = [
        ("Имя", user_name),
        ("Комментарий", comment),
        ("Email", email),
        ("Телефон", f"+{phone_e164}" if phone_e164 else None),
    ]
    rows_html = "\n".join(
        f"""
        <tr>
            <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;background:#f8fafc;font-weight:600;">{html.escape(label)}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">{_cell(value)}</td>
        </tr>
        """
        for label, value in rows
        if value
    )
    if not rows_html:
        rows_html = """
        <tr>
            <td colspan="2" style="padding:12px;">Без дополнительных данных.</td>
        </tr>
        """

    return f"""
    <html>
      <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;">
        <div style="max-width:680px;margin:0 auto;padding:24px;">
          <div style="background:#ffffff;border:1px solid #e5e7eb;padding:24px;">
            <h2 style="margin:0 0 12px 0;">Новая заявка с сайта</h2>
            <p style="margin:0 0 16px 0;line-height:1.5;">
              На сайте подрядчик.com оставили заявку на обратный звонок.
            </p>
            <table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;border:1px solid #e5e7eb;">
              {rows_html}
            </table>
          </div>
        </div>
      </body>
    </html>
    """


def _build_email_message(
    recipient_email: str,
    sender_email: str,
    sender_name: str,
    subject: str,
    user_name: Optional[str],
    comment: Optional[str],
    email: Optional[str],
    phone_e164: Optional[str],
) -> EmailMessage:
    plain_text = _build_message(user_name, comment, email, phone_e164)
    html_text = _build_html_message(user_name, comment, email, phone_e164)
    safe_sender_email = _normalize_email_address(sender_email)
    safe_recipient_email = _normalize_email_address(recipient_email)

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, safe_sender_email))
    msg["To"] = safe_recipient_email
    if email:
        msg["Reply-To"] = email
    msg["X-Entity-Ref-ID"] = email or phone_e164 or "callback-request"
    msg.set_content(plain_text)
    msg.add_alternative(html_text, subtype="html")
    return msg


def _send_email_to_manager(
    recipient_email: str,
    user_name: Optional[str],
    comment: Optional[str],
    email: Optional[str],
    phone_e164: Optional[str],
) -> None:
    """Отправляет письмо владельцу сайта через обычный SMTP."""
    smtp_host = _require_env("SMTP_HOST")
    smtp_port = int(_require_env("SMTP_PORT"))
    smtp_username = _normalize_email_address(_require_env("SMTP_USERNAME"))
    smtp_password = _require_env("SMTP_PASSWORD")
    sender_email = _normalize_email_address(_require_env("SMTP_FROM_EMAIL"))
    sender_name = _require_env("SMTP_FROM_NAME")
    subject = _require_env("CALLBACK_EMAIL_SUBJECT")
    if smtp_port == 465:
        use_ssl = True
        use_starttls = False
    elif smtp_port == 587:
        use_ssl = False
        use_starttls = True
    else:
        raise Internal("Unsupported SMTP_PORT. Use 465 or 587.")

    msg = _build_email_message(
        recipient_email=recipient_email,
        sender_email=sender_email,
        sender_name=sender_name,
        subject=subject,
        user_name=user_name,
        comment=comment,
        email=email,
        phone_e164=phone_e164,
    )

    tls_context = ssl.create_default_context()

    try:
        if use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10, context=tls_context) as client:
                client.login(smtp_username, smtp_password)
                client.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as client:
                client.ehlo()
                if use_starttls:
                    client.starttls(context=tls_context)
                    client.ehlo()
                client.login(smtp_username, smtp_password)
                client.send_message(msg)
    except Exception as e:
        logger.error(
            "smtp.send_failed",
            error=str(e),
            trace=traceback.format_exc(),
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            recipient=recipient_email,
        )
        raise

    logger.info(
        "smtp.sent",
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        recipient=recipient_email,
        reply_to=email,
    )


def handler(event, context):  # noqa: D401
    logger.info("callback_request.invoked")
    logger.info(
        "callback_request.request_raw",
        request_text=json.dumps(
            {
                "method": ((event or {}).get("requestContext") or {}).get("http", {}).get("method")
                or (event or {}).get("httpMethod"),
                "path": ((event or {}).get("requestContext") or {}).get("http", {}).get("path")
                or (event or {}).get("path"),
                "headers": logger.redact_headers((event or {}).get("headers") or {}),
                "query": (event or {}).get("queryStringParameters") or {},
                "path_params": (event or {}).get("pathParameters") or {},
                "body": (event or {}).get("body"),
                "isBase64Encoded": bool((event or {}).get("isBase64Encoded")),
                "requestContext": (event or {}).get("requestContext") or {},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
    )

    pre = handle_preflight((event or {}).get("headers") or {}, allow_origin=os.getenv("CORS_ALLOW_ORIGIN", "*"))
    if pre:
        return _with_base_headers(pre)

    try:
        req = parse_event(event)
        body = req.get("body_dict") or {}
    except EventParseError as e:
        logger.warn("callback_request.parse_error", error=str(e), trace=traceback.format_exc())
        return _with_base_headers(bad_request(f"Invalid request: {e}"))

    logger.info(
        "callback_request.request",
        request_text=_format_request_text(event or {}, req),
        headers=logger.redact_headers((event or {}).get("headers") or {}),
        payload=body,
    )

    contract_error = _validate_contract_hashes(req.get("headers") or {})
    if contract_error:
        return contract_error

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

    try:
        recipient_email = _require_env("CALLBACK_NOTIFY_EMAIL")
        _send_email_to_manager(
            recipient_email=recipient_email,
            user_name=user_name,
            comment=comment,
            email=email,
            phone_e164=phone_e164,
        )
    except Exception as e:
        logger.error(
            "callback_request.send_failed",
            error=str(e),
            trace=traceback.format_exc(),
            payload=_build_message(user_name, comment, email, phone_e164),
        )
        return _with_base_headers(server_error("Failed to send email"))

    logger.info(
        "callback_request.sent",
        recipient_email=recipient_email,
        lead_phone=phone_e164,
        email=email,
    )
    return _with_base_headers(ok({"message": "Callback request sent via email."}))
```
