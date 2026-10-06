import asyncio
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from eventdesk.api import create_app
from eventdesk.http_policy import retry_delay
from eventdesk.schemas import Event
from eventdesk.store import Job
from eventdesk.worker import Worker


def test_retry_after_seconds_and_http_dates():
    # PLACEHOLDER: deterministic timestamps and server responses for protocol boundaries.
    now = 1700000000.0
    assert retry_delay("45", now) == 45
    assert retry_delay(format_datetime(datetime.fromtimestamp(now + 45, UTC), usegmt=True), now) == 45
    for raw in (None, "NaN", "Infinity", "-1", "1.2", "secret text", "0", "9" * 1000):
        assert retry_delay(raw, now) == 2
    assert retry_delay(format_datetime(datetime.fromtimestamp(now - 45, UTC), usegmt=True), now) == 2


def test_server_delay_prevents_repost_and_expires_without_revising_outbox(settings, store, model):
    # PLACEHOLDER: synthetic TEST event exercises retry scheduling, not official coverage.
    event = Event(id="delay-delivery", event_id="delay-event", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    posts = []
    def handler(request):
        posts.append(json.loads(request.content))
        return httpx.Response(429, headers={"Retry-After": "45"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            worker = Worker(replace(settings, fixture_mode=False), store, model, http)
            first = store.claim(time.time())
            await worker.process(first)
            assert store.claim(time.time() + 10) is None
            second = store.claim(time.time() + 46)
            assert second.payload == posts[0]
            # SOURCE: the mission's five-minute budget; longer server cooldown must expire this event.
            worker.http = httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(503, headers={"Retry-After": "300"})))
            try:
                await worker.process(second)
            finally:
                await worker.http.aclose()
    asyncio.run(run())
    assert store.public_event(event.event_id)["state"] == "expired"
    assert store.claim(time.time() + 1000) is None


def test_public_event_never_reflects_arbitrary_submission_response(settings, store):
    event = Event(id="response-delivery", event_id="response-event", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    work = store.claim(time.time())
    store.persist_prediction(work.id, {"event_id": event.event_id, "predictions": []}, {}, "fixture", None)
    response = {"status": "never-export-status", "echo": "never-export-key", "nested": {"url": "never-export"}}
    store.finish(work.id, response, "api_accepted", time.time())
    client = TestClient(create_app(settings, store))
    detail = client.get("/api/events/response-event").json()
    listing = client.get("/api/predictions").json()
    assert detail["submission_response"] == {"state": "api_accepted", "http_status": 201}
    assert listing[0]["submission_status"] == "api_accepted"
    assert "never-export" not in json.dumps([detail, listing])
    with Session(store.engine) as session:
        assert session.get(Job, work.id).response == response
