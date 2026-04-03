# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from handlers_employee_finance import _coerce_datetime_utc


def norm_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_month_window_utc(year: int, month: int) -> Tuple[datetime, datetime]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return start, end


def parse_day_window_utc(date_str: str) -> Tuple[datetime, datetime]:
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


def hours_from_seconds(seconds: int) -> float:
    if seconds <= 0:
        return 0.0
    return round(seconds / 3600.0, 2)


def overlap_range_seconds(
    start: Optional[datetime],
    end: Optional[datetime],
    window_start: datetime,
    window_end: datetime,
) -> int:
    if start is None or end is None or end <= start:
        return 0
    bounded_start = max(start, window_start)
    bounded_end = min(end, window_end)
    if bounded_end <= bounded_start:
        return 0
    return int((bounded_end - bounded_start).total_seconds())


def split_interval_by_day(
    start: datetime,
    end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> Dict[str, int]:
    result: Dict[str, int] = {}
    if end <= start:
        return result

    current = max(start, window_start)
    bounded_end = min(end, window_end)
    if bounded_end <= current:
        return result

    while current < bounded_end:
        next_day = datetime(
            current.year,
            current.month,
            current.day,
            tzinfo=timezone.utc,
        ) + timedelta(days=1)
        segment_end = min(next_day, bounded_end)
        seconds = int((segment_end - current).total_seconds())
        if seconds > 0:
            key = current.date().isoformat()
            result[key] = result.get(key, 0) + seconds
        current = segment_end

    return result


def add_interval_breakdown(
    target: Dict[str, int],
    *,
    start: Optional[datetime],
    end: Optional[datetime],
    window_start: datetime,
    window_end: datetime,
) -> None:
    if start is None or end is None or end <= start:
        return
    for key, seconds in split_interval_by_day(start, end, window_start, window_end).items():
        target[key] = target.get(key, 0) + seconds


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for raw in values:
        value = norm_str(raw)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return default
        try:
            return int(raw)
        except Exception:
            return default
    return default


def interval_payload(
    *,
    object_id: str,
    source_type: str,
    started_at: Optional[datetime],
    ended_at: Optional[datetime],
    source_id: str = "",
) -> Optional[Dict[str, Any]]:
    if started_at is None or ended_at is None or ended_at <= started_at:
        return None
    return {
        "object_id": norm_str(object_id),
        "source_type": norm_str(source_type),
        "source_id": norm_str(source_id),
        "started_at": started_at,
        "ended_at": ended_at,
    }
