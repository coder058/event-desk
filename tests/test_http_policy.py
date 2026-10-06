import asyncio
import json
import time
from dataclasses import replace
from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest
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


@pytest.mark.parametrize("body", [b'[]', b'{"score": NaN}', b'not-json', b'\xff', b'x' * (1024 * 1024 + 1)],
                         ids=['array', 'nonfinite', 'invalid-json', 'non-utf8', 'oversized'])
def test_observed_201_invalid_body_never_causes_repost(settings, store, model, body):
    event = Event(id="invalid-body", event_id="invalid-body", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    posts = []
    def handler(request):
        posts.append(json.loads(request.content))
        return httpx.Response(201, content=body)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await Worker(replace(settings, fixture_mode=False), store, model, http).process(store.claim(time.time()))
    asyncio.run(run())
    assert len(posts) == 1
    assert store.claim(time.time()+10) is None
    assert store.public_event(event.event_id)["state"] == "api_accepted"
    with Session(store.engine) as session:
        receipt = session.get(Job, 1).response
        assert receipt["http_status"] == 201
        assert receipt["body_state"] in ("invalid_json_object", "exceeds_memory_ceiling")


@pytest.mark.parametrize("headers_seen", [False, True])
def test_submission_entire_attempt_bounded_and_unknown_result_reuses_outbox(
        settings, store, model, headers_seen):
    event = Event(id="stalled-submit", event_id="stalled-submit", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    posts = []
    class StalledBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b"never"
    async def handler(request):
        posts.append(json.loads(request.content))
        if not headers_seen:
            await asyncio.Event().wait()
        return httpx.Response(201, stream=StalledBody())
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            work = store.claim(time.time())
            # PLACEHOLDER: inject a 50 ms attempt deadline after database setup; not a production latency claim.
            work = replace(work, deadline=time.time()+.05)
            # GUESS: test watchdog catches an unbounded header/body await. # UNCALIBRATED GUESS
            async with asyncio.timeout(2):
                await Worker(replace(settings, fixture_mode=False), store, model, http).process(work)
    asyncio.run(run())
    with Session(store.engine) as session:
        row = session.get(Job, 1)
        assert row.payload == posts[0]
        if headers_seen:
            assert row.state == "api_accepted"
            assert row.response == {"http_status": 201, "body_state": "read_incomplete"}
        else:
            assert row.state == "pending"
            assert row.error == "submission_transport_uncertain"
            assert store.claim(time.time()+3).payload == posts[0]


def test_rate_limit_headers_do_not_wait_for_stalled_body(settings, store, model):
    event = Event(id="rate-stall", event_id="rate-stall", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    class StalledBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b"never"
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request: httpx.Response(429, headers={"Retry-After": "45"}, stream=StalledBody()))) as http:
            # GUESS: test watchdog only; no network latency promise. # UNCALIBRATED GUESS
            async with asyncio.timeout(2):
                await Worker(replace(settings, fixture_mode=False), store, model, http).process(store.claim(time.time()))
    asyncio.run(run())
    assert store.claim(time.time()+10) is None
    assert store.claim(time.time()+46) is not None
