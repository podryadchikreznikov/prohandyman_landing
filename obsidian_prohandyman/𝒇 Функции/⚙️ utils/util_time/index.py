from __future__ import annotations
from datetime import datetime, timezone

def now_utc() -> datetime: return datetime.now(timezone.utc)
def parse_iso_utc(s: str) -> datetime: return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

def to_ts_us(dt: datetime) -> int: return int(dt.timestamp()*1_000_000)
def from_ts_us(us: int) -> datetime: return datetime.fromtimestamp(us/1_000_000, tz=timezone.utc)

def to_ts_ms(dt: datetime) -> int: return int(dt.timestamp()*1_000)
def from_ts_ms(ms: int) -> datetime: return datetime.fromtimestamp(ms/1_000, tz=timezone.utc)