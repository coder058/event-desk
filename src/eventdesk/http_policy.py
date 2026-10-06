"""HTTP scheduling; server retry instructions cannot cause a busy retry loop."""
from __future__ import annotations

from email.utils import parsedate_to_datetime


def retry_delay(header: str | None, now: float) -> float:
    # GUESS: existing two-second transport retry floor; measure actual server behavior. # UNCALIBRATED GUESS
    floor = 2.0
    if header is None:
        return floor
    # SOURCE: RFC 9110 section 10.2.3 permits nonnegative integer seconds or HTTP-date.
    raw = header.strip()
    if raw.isascii() and raw.isdecimal():
        try:
            delay = float(int(raw))
        except (ValueError, OverflowError):
            return floor
        # Infinite instructions are not finite scheduling times; no unbounded conversion to timestamp.
        import math
        return max(floor, delay) if math.isfinite(delay) else floor
    try:
        when = parsedate_to_datetime(raw)
        if when.tzinfo is None:
            return floor
        return max(floor, when.timestamp() - now)
    except (ValueError, TypeError, OverflowError):
        return floor
