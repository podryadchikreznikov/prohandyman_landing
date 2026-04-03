# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, List, Optional

from handlers_employee_finance import _coerce_datetime_utc


def norm_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_day_window_utc(date_str: str):
    start = datetime.strptime(norm_str(date_str), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    return start, start + timedelta(days=1)


def to_datetime_utc(value: Any) -> Optional[datetime]:
    return _coerce_datetime_utc(value)


def to_iso_utc(value: Any) -> Optional[str]:
    dt = to_datetime_utc(value)
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def chunked(values: List[str], chunk_size: int) -> Iterable[List[str]]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    for i in range(0, len(values), chunk_size):
        yield values[i : i + chunk_size]
