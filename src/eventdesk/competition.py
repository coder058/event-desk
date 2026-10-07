"""Read-only official calendar/counter observations, isolated from prediction work."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections import Counter
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from eventdesk.config import COMPETITION_ORIGIN, Settings
from eventdesk.store import Store

# SOURCE: binding Q4 2026 rules, scoring period October 12 through December 15.
SCORING_START = date(2026, 10, 12)
SCORING_END = date(2026, 12, 15)
# GUESS: capacity display uses the announced registration timezone; scoring-event
# eligibility is determined by organizers, not this calendar-date grouping.
# UNCALIBRATED GUESS
CENTRAL = ZoneInfo("America/Chicago")
# GUESS: ten-minute observation cadence, fifteen-second total request guard and
# sixteen-MiB calendar ceiling; adjust using actual API/host behavior.
# UNCALIBRATED GUESS
POLL_SECONDS = 600
READ_SECONDS = 15
MAX_BYTES = 16 * 1024 * 1024

# SOURCE: official examples SubmissionHealth response schema (rolling 24 hours).
COUNTERS = ("webhook_n_2xx", "webhook_n_4xx", "webhook_n_5xx", "webhook_n_timeout",
            "webhook_consecutive_failures", "submission_n_total", "submission_n_duplicate",
            "submission_n_late", "submission_n_pre_broadcast", "submission_n_invalid_event")
TIMESTAMPS = ("webhook_last_delivery_at", "submission_last_at", "last_test_prediction_at")


class CalendarEvent(BaseModel):
    # Unknown API fields are ignored, not exported to public monitoring.
    model_config = ConfigDict(extra="ignore")
    event_id: str = Field(min_length=1)
    event_type: str
    timing_category: str
    event_datetime: datetime
    knowledge_cutoff: datetime | None = None

    @field_validator("event_datetime", "knowledge_cutoff")
    @classmethod
    def aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Official calendar timestamp needs timezone")
        return value


def parse_calendar(raw: bytes) -> list[dict[str, Any]]:
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("Official calendar must be an array")
    events = [CalendarEvent.model_validate(item).model_dump(mode="json") for item in data]
    if len({event["event_id"] for event in events}) != len(events):
        raise ValueError("Official calendar contains duplicate event identifiers")
    return events


def parse_health(raw: bytes) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Official health must be an object")
    result: dict[str, Any] = {}
    for name in COUNTERS:
        value = data.get(name)
        if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
            raise ValueError("Invalid official counter")
        result[name] = value
    for name in TIMESTAMPS:
        value = data.get(name)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError("Invalid official timestamp")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("Official timestamp needs timezone")
            result[name] = parsed.isoformat()
        else:
            result[name] = None
    # submission_id, arbitrary status/error strings and future fields never leave this parser.
    return result


def summarize_calendar(events: list[dict[str, Any]], observed_at: float) -> dict[str, Any]:
    dates: Counter[str] = Counter()
    window_dates: Counter[str] = Counter()
    due = 0
    for event in events:
        instant = datetime.fromisoformat(event["event_datetime"])
        day = instant.astimezone(CENTRAL).date()
        dates[day.isoformat()] += 1
        if SCORING_START <= day <= SCORING_END:
            window_dates[day.isoformat()] += 1
            if instant.timestamp() <= observed_at:
                due += 1
    return {"scheduled_entries": len(events), "event_types": dict(Counter(e["event_type"] for e in events)),
        "timing_categories": dict(Counter(e["timing_category"] for e in events)),
        "first_calendar_day_central": min(dates) if dates else None,
        "last_calendar_day_central": max(dates) if dates else None,
        "scheduled_in_scoring_window": sum(window_dates.values()),
        "scheduled_due_in_scoring_window": due,
        "scoring_window_daily_counts_central": dict(sorted(window_dates.items())),
        "peak_scoring_window_day_central": max(window_dates, key=lambda day: (window_dates[day], day))
                                             if window_dates else None,
        "peak_scoring_window_entries": max(window_dates.values()) if window_dates else None,
        "official_eligible_coverage": None,
        "limits": "Calendar entries are mutable schedules, not broadcasts or the final eligible scored set. "
                  "Official health counters are a separate rolling 24-hour snapshot; coverage is not inferred."}


async def read_bytes(http: httpx.AsyncClient, route: str, api_key: str) -> bytes:
    # Only these GET paths exist here. No test-delivery or prediction mutation path.
    if route not in ("events", "health"):
        raise ValueError("Read-only competition route required")
    async with asyncio.timeout(READ_SECONDS):
        async with http.stream("GET", COMPETITION_ORIGIN+"/"+route,
                               headers={"X-API-Key": api_key}, follow_redirects=False) as response:
            if response.status_code != 200:
                raise ValueError("Official read status "+str(response.status_code))
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_BYTES:
                    raise ValueError("Official metadata exceeds bounded read")
    return bytes(raw)


async def observe(settings: Settings, store: Store, http: httpx.AsyncClient) -> None:
    if settings.fixture_mode:
        raise ValueError("Official observations are disabled in fixtures")
    for slot, submission in settings.submissions.items():
        try:
            started_at = time.time()
            raw_calendar = await read_bytes(http, "events", submission.api_key)
            calendar = parse_calendar(raw_calendar)
            raw_health = await read_bytes(http, "health", submission.api_key)
            health = parse_health(raw_health)
            observed_at = time.time()
            await asyncio.to_thread(store.record_competition_observation, slot, calendar, health,
                hashlib.sha256(raw_calendar).hexdigest(), hashlib.sha256(raw_health).hexdigest(),
                summarize_calendar(calendar, observed_at), started_at, observed_at)
            await asyncio.to_thread(store.pulse, "competition:"+slot,
                                    {"state": "observed", "scheduled_entries": len(calendar)}, observed_at)
        except Exception as exc:
            # SDK/HTTP exceptions may contain keys or response text; record only type.
            await asyncio.to_thread(store.pulse, "competition:"+slot,
                                    {"state": "observation_failed", "error_type": type(exc).__name__}, time.time())


async def run() -> None:
    settings = Settings.from_env()
    if settings.fixture_mode:
        raise ValueError("Official collector must not run in fixture compose")
    store = Store(settings.database_url)
    # Credential routing and TLS roots must not inherit ambient proxy/CA overrides.
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as http:
        while True:
            await observe(settings, store, http)
            await asyncio.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    asyncio.run(run())
