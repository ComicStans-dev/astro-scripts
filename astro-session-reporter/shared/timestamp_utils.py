"""
Module: timestamp_utils

Utilities for parsing timestamps from multiple sources (FITS headers, log files), normalizing them to UTC, and providing comparison helpers.
"""
from datetime import datetime, timezone, timedelta
import re
from typing import Optional

ISO_PAT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z)?$")

LOG_PAT_SLASH = "%Y/%m/%d %H:%M:%S"
LOG_PAT_DASH  = "%Y-%m-%d %H:%M:%S"


def _try_parse(fmt: str, value: str):
    try:
        return datetime.strptime(value, fmt)
    except ValueError:
        return None


def parse_any(ts: str, guiding_start: Optional[datetime] = None):
    """Parse *ts* from any known format into an *aware* UTC datetime.

    If *ts* is a float / int string and *guiding_start* is given, treat it as
    seconds since guiding began.
    """
    if ts is None:
        return None

    ts = ts.strip()

    # 1) ISO 8601 (DATE-OBS) – assume already UTC when endswith Z or treat naive as UTC.
    if ISO_PAT.match(ts):
        dt = datetime.fromisoformat(ts.replace("Z", ""))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    # 2) Slash log format
    dt = _try_parse(LOG_PAT_SLASH, ts)
    if dt:
        return dt.replace(tzinfo=timezone.utc)  # treat NINA local as UTC for now (TODO)

    # 3) Dash log format
    dt = _try_parse(LOG_PAT_DASH, ts)
    if dt:
        return dt.replace(tzinfo=timezone.utc)

    # 4) Seconds since guiding start
    if guiding_start:
        try:
            seconds = float(ts)
            return guiding_start + timedelta(seconds=seconds)
        except ValueError:
            pass

    raise ValueError(f"Unrecognised timestamp: {ts}")


def to_utc(dt: datetime):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def within(dt1: datetime, dt2: datetime, tolerance_seconds: float = 2.0):
    """Return True if *dt1* and *dt2* differ by <= tolerance_seconds."""
    delta = abs((to_utc(dt1) - to_utc(dt2)).total_seconds())
    return delta <= tolerance_seconds 