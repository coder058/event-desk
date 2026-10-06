"""HTTP scheduling; server retry instructions cannot cause a busy retry loop."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx


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


@dataclass(frozen=True)
class SubmissionReceipt:
    http_status: int
    body: dict[str, Any]
    retry_after: str | None


async def submit_bounded(http: httpx.AsyncClient, url: str, *, payload: dict[str, Any],
                         headers: dict[str, str], remaining: float) -> SubmissionReceipt:
    """A phase timeout includes connect, headers and body; an observed 201 is never reposted for body errors."""
    if remaining <= 0:
        raise TimeoutError("Submission deadline exhausted")
    # SOURCE: inherited 15-second submission attempt budget, capped by the original event deadline.
    budget = min(15, remaining)
    status: int | None = None
    retry_after: str | None = None
    try:
        async with asyncio.timeout(budget):
            async with http.stream("POST", url, json=payload, headers=headers, timeout=budget) as response:
                status, retry_after = response.status_code, response.headers.get("Retry-After")
                if status != 201:
                    # Do not wait for an irrelevant rejected/rate-limited response body.
                    return SubmissionReceipt(status, {}, retry_after)
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    # GUESS: 1 MiB response cap protects worker memory; measure official response sizes. # UNCALIBRATED GUESS
                    if len(raw) > 1024 * 1024:
                        return SubmissionReceipt(status, {"http_status": status,
                            "body_state": "exceeds_memory_ceiling"}, retry_after)
                try:
                    body = json.loads(raw)
                    json.dumps(body, allow_nan=False)
                    if not isinstance(body, dict):
                        raise ValueError("Acknowledgement is not an object")
                except (ValueError, UnicodeError, RecursionError, OverflowError):
                    return SubmissionReceipt(status, {"http_status": status,
                        "body_state": "invalid_json_object"}, retry_after)
                return SubmissionReceipt(status, body, retry_after)
    except (httpx.HTTPError, OSError, TimeoutError):
        if status == 201:
            # SOURCE: api_accepted means observed HTTP 201 only, not competition eligibility.
            # The server already responded; missing body must not cause a duplicate POST.
            return SubmissionReceipt(status, {"http_status": status,
                "body_state": "read_incomplete"}, retry_after)
        raise
