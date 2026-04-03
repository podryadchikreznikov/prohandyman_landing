# -*- coding: utf-8 -*-
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from common import safe_json
from handlers_employee_finance import _coerce_datetime_utc


def norm_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_date_utc(date_str: str) -> Tuple[datetime, datetime]:
    dt = datetime.strptime(str(date_str or "").strip(), "%Y-%m-%d").replace(
        tzinfo=timezone.utc
    )
    return dt, dt + timedelta(days=1)


def normalize_ids_list(raw: Any) -> List[str]:
    parsed = safe_json(raw)
    if not isinstance(parsed, list):
        return []
    out: List[str] = []
    seen = set()
    for item in parsed:
        sid = norm_str(item)
        if not sid or sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def norm_ids(values: Any) -> List[str]:
    ids = []
    for value in values or []:
        if value is None:
            continue
        sid = str(value).strip()
        if sid:
            ids.append(sid)
    seen = set()
    out = []
    for sid in ids:
        if sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


def to_iso_utc(value: Any) -> Optional[str]:
    if value is None:
        return None

    dt = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        ts = float(value)
        abs_ts = abs(ts)
        if abs_ts >= 1_000_000_000_000_000_000:
            dt = datetime.fromtimestamp(ts / 1_000_000_000, tz=timezone.utc)
        elif abs_ts >= 1_000_000_000_000_000:
            dt = datetime.fromtimestamp(ts / 1_000_000, tz=timezone.utc)
        elif abs_ts >= 1_000_000_000_000:
            dt = datetime.fromtimestamp(ts / 1_000, tz=timezone.utc)
        else:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            return to_iso_utc(int(raw))
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def candidate(
    event_type: str,
    event_at: Any,
    *,
    status: str,
    is_present: bool,
    event_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    dt = _coerce_datetime_utc(event_at)
    if dt is None:
        return None
    return {
        "event_type": event_type,
        "event_at": dt,
        "status": status,
        "is_present": is_present,
        "event_id": event_id,
    }


def pick_latest_candidate(
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    priority = {"finished": 2, "present": 1, "absent": 0}
    return max(
        candidates,
        key=lambda item: (
            item.get("event_at") or datetime(1970, 1, 1, tzinfo=timezone.utc),
            priority.get(norm_str(item.get("status")).lower(), -1),
        ),
    )


def role_label_from_role_type(role_type: str) -> Optional[str]:
    normalized = norm_str(role_type).lower()
    if normalized == "worker":
        return "Рабочий"
    if normalized == "foreman":
        return "Бригадир"
    return None


def extract_profile_role_label(profile: Any) -> Optional[str]:
    if not isinstance(profile, dict):
        return None
    tags = profile.get("tags_json")
    if not isinstance(tags, list):
        return None
    for raw in tags:
        if isinstance(raw, str):
            sid = raw.strip()
            if sid:
                return sid
            continue
        if isinstance(raw, dict):
            for key in ("label", "name", "title", "role"):
                value = raw.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None
