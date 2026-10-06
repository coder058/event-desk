import asyncio
import hashlib
import json
from datetime import datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eventdesk.competition import observe, parse_calendar, parse_health, read_bytes, summarize_calendar
from eventdesk.store import CompetitionCalendar, CompetitionObservation


def calendar_bytes():
    # PLACEHOLDER: fabricated calendar, including a Central-time scoring-boundary case.
    return json.dumps([
        {"event_id": "before", "event_type": "EARNINGS_RELEASE", "timing_category": "SCHEDULED",
         "event_datetime": "2026-10-12T03:00:00Z", "knowledge_cutoff": None,
         "unknown_private_field": "never-export"},
        {"event_id": "within", "event_type": "FUTURE_EVENT_TYPE", "timing_category": "SCHEDULED",
         "event_datetime": "2026-10-12T13:00:00Z", "knowledge_cutoff": "2026-10-12T12:00:00Z"}
    ]).encode()


def test_calendar_coverage_is_not_inferred_from_schedules_and_rolling_counters():
    events = parse_calendar(calendar_bytes())
    assert "never-export" not in json.dumps(events)
    summary = summarize_calendar(events, datetime.fromisoformat("2026-10-12T14:00:00Z").timestamp())
    assert summary["scheduled_entries"] == 2
    assert summary["scheduled_due_in_scoring_window"] == 1
    assert summary["scoring_window_daily_counts_central"] == {"2026-10-12": 1}
    assert summary["official_eligible_coverage"] is None
    parsed = parse_health(b'{"submission_id":"never-export","webhook_last_status":"never-export",'
                          b'"submission_n_total":1,"webhook_n_2xx":2}')
    assert parsed["submission_n_total"] == 1
    assert parsed["submission_n_late"] is None
    assert "never-export" not in json.dumps(parsed)
    with pytest.raises(ValueError):
        parse_health(b'{"submission_n_total":true}')
    with pytest.raises(ValueError):
        parse_health(b'{"webhook_last_delivery_at":"2026-10-12T14:00:00"}')
    with pytest.raises(ValueError):
        parse_calendar(json.dumps(events+events).encode())


def test_official_reads_are_get_only_and_failures_preserve_prior_snapshot(settings, store):
    production = type(settings)(settings.database_url, settings.model_path, settings.submissions,
                                False, settings.material_hosts)
    calls = []
    fail = False
    calendar = calendar_bytes()
    health = b'{"submission_n_total":0,"submission_id":"never-export"}'
    def handler(request):
        calls.append((request.method, request.url.path))
        if fail:
            return httpx.Response(401, text="never-export secret or error body")
        return httpx.Response(200, content=calendar if request.url.path.endswith("events") else health)
    async def run():
        nonlocal fail
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await observe(production, store, http)
            await observe(production, store, http)
            fail = True
            await observe(production, store, http)
            with pytest.raises(ValueError):
                await observe(settings, store, http)
    asyncio.run(run())
    assert all(method == "GET" and path in ("/v1/events", "/v1/health") for method, path in calls)
    with Session(store.engine) as session:
        assert session.scalar(select(func.count()).select_from(CompetitionCalendar)) == 1
        assert session.scalar(select(func.count()).select_from(CompetitionObservation)) == 2
    public = store.competition_overview()
    assert "never-export" not in json.dumps(public)
    snapshot = public["submissions"]["s1"]
    assert snapshot["calendar_raw_sha256"] == hashlib.sha256(calendar).hexdigest()
    assert snapshot["collector"]["state"] == "observation_failed"
    assert snapshot["official_rolling_24h_counters"]["submission_n_total"] == 0
    assert public["official_eligible_coverage"] is None


def test_observation_response_and_route_are_bounded(monkeypatch):
    import eventdesk.competition as module
    # PLACEHOLDER: tiny fixture cap verifies the production bounded streaming logic.
    monkeypatch.setattr(module, "MAX_BYTES", 4)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"01234"))) as http:
            with pytest.raises(ValueError):
                await read_bytes(http, "events", "fixture-key")
            with pytest.raises(ValueError):
                await read_bytes(http, "predictions", "fixture-key")
    asyncio.run(run())
