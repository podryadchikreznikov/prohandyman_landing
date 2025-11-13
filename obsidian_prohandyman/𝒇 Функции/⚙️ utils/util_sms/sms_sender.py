"""Утилиты для отправки SMS через SMSC.ru."""

from __future__ import annotations

import os
from typing import Optional

import requests

API_URL = "https://smsc.ru/sys/send.php"


def send_sms_code(phone: str, code: str) -> bool:
    """Отправляет одноразовый код пользователю."""
    login = os.getenv("SMSC_LOGIN")
    password = os.getenv("SMSC_PASSWORD")
    if not login or not password:
        return False

    phone_clean = "".join(filter(str.isdigit, phone))
    if not phone_clean:
        return False

    params = {
        "login": login,
        "psw": password,
        "phones": phone_clean,
        "mes": f"Ваш код подтверждения: {code}",
        "fmt": 3,
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError):
        return False

    if payload.get("error"):
        return False

    return True


def validate_phone_number(phone: str) -> Optional[str]:
    """Возвращает номер в формате 7909… либо None."""
    if not phone:
        return None

    cleaned = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    if cleaned.startswith("8") and len(cleaned) == 11:
        cleaned = "7" + cleaned[1:]

    if len(cleaned) == 10:
        cleaned = "7" + cleaned

    if len(cleaned) == 11 and cleaned.startswith("7"):
        return cleaned

    return None

