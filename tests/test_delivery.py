import asyncio
import base64
import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
import pytest
from conftest import SECRET
from fastapi.testclient import TestClient

from eventdesk.api import create_app
from eventdesk.schemas import Event
from eventdesk.store import ConflictError
from eventdesk.worker import Worker


def event(number=1, kind="EARNINGS_RELEASE"):
    return Event(id=f"delivery-{number}", event_id=f"event-{number}", event_type=kind,
                 knowledge_cutoff=datetime.now(UTC),
                 focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])


def signed(raw, delivery_id):
    timestamp = str(int(time.time()))
    key = base64.urlsafe_b64decode(SECRET.removeprefix("whsec_"))
    signature = base64.b64encode(hmac.new(key, delivery_id.encode() + b"." + timestamp.encode() + b"." + raw,
                                         hashlib.sha256).digest()).decode()
    return {"Webhook-Id": delivery_id, "Webhook-Timestamp": timestamp,
            "Webhook-Signature": "v1," + signature, "Content-Type": "application/json"}


def test_receiver_commits_before_ack_and_preserves_duplicate_deadline(settings, store):
    client = TestClient(create_app(settings, store))
    e = event()
    raw = e.model_dump_json().encode()
    assert client.post("/competition/webhook", content=raw, headers=signed(raw, e.id)).status_code == 200
    assert store.health()["states"] == {"pending": 1}
    first = store.claim(time.time())
    assert first is not None
    assert client.post("/competition/webhook", content=raw, headers=signed(raw, e.id)).status_code == 200
    store.recover()
    second = store.claim(time.time())
    assert second.deadline == first.deadline
    assert client.post("/competition/webhook", content=raw + b" ", headers=signed(raw, e.id)).status_code == 401


def test_nonstandard_json_numbers_rejected_before_durable_ack(settings, store):
    client = TestClient(create_app(settings, store))
    e = event()
    payload = e.model_dump(mode="json")
    payload["extra_invalid"] = float("nan")
    raw = json.dumps(payload).encode()
    assert client.post("/competition/webhook", content=raw, headers=signed(raw, e.id)).status_code == 400
    assert store.health()["states"] == {}


def test_slow_stream_cannot_spend_the_receipt_budget_before_database_work(settings, store, monkeypatch):
    import eventdesk.api
    # GUESS: injected short test guard; production retains the documented ten-second budget.
    monkeypatch.setattr(eventdesk.api, "RECEIPT_GUARD_SECONDS", .02)
    e = event()
    raw = e.model_dump_json().encode()

    async def slow_body():
        yield raw[:1]
        await asyncio.Event().wait()
        yield raw[1:]

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(settings, store)),
                                     base_url="http://fixture") as client:
            response = await client.post("/competition/webhook", content=slow_body(), headers=signed(raw, e.id))
            assert response.status_code == 503
    asyncio.run(run())
    assert store.health()["states"] == {}


def test_concurrent_duplicate_and_immutable_outbox(store):
    e = event()
    raw = e.model_dump_json().encode()
    with ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: store.receive("s1", e.id, raw, e, time.time()), range(24)))
    assert sum(values) == 1
    work = store.claim(time.time())
    payload = {"event_id": e.event_id, "predictions": [{"identifier_value": "FIXTURE", "predicted_percentile": .6}]}
    store.persist_prediction(work.id, payload, {}, "model-test", None)
    store.persist_prediction(work.id, payload, {}, "model-test", None)
    with pytest.raises(ConflictError):
        store.persist_prediction(work.id, {**payload, "predictions": []}, {}, "different", None)


def test_uncertain_submit_retries_identical_persisted_prediction(settings, store, model):
    e = event(kind="TEST")
    store.receive("s1", e.id, e.model_dump_json().encode(), e, time.time())
    production = type(settings)(settings.database_url, settings.model_path, settings.submissions,
                                False, frozenset())
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        if len(captured) == 1:
            raise httpx.ReadTimeout("fixture uncertainty")
        return httpx.Response(201, json={"status": "test_accepted"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            worker = Worker(production, store, model, http)
            first = store.claim(time.time())
            await worker.process(first)
            store.recover()
            store.retry(first.id, "test immediate retry", 0, time.time())
            second = store.claim(time.time())
            assert second.payload == captured[0]
            await worker.process(second)
    asyncio.run(run())
    assert len(captured) == 2 and captured[0] == captured[1]
    assert store.health()["states"] == {"api_accepted": 1}


def test_busy_day_400_events_recoverable_coverage(settings, store, model):
    # SOURCE: mission's requested 400-event synthetic busy-day plumbing test. Not real score coverage.
    client = TestClient(create_app(settings, store))
    start = time.perf_counter()
    for number in range(400):
        e = event(number)
        raw = e.model_dump_json().encode()
        assert client.post("/competition/webhook", content=raw, headers=signed(raw, e.id)).status_code == 200
    store.recover()
    async def run():
        async with httpx.AsyncClient() as http:
            worker = Worker(settings, store, model, http)
            async def drain():
                while True:
                    work = await asyncio.to_thread(store.claim, time.time())
                    if work is None:
                        return
                    await worker.process(work)
            await asyncio.gather(*(drain() for _ in range(8)))
    asyncio.run(run())
    elapsed = time.perf_counter() - start
    assert store.health()["states"] == {"simulated": 400}
    assert elapsed < 300  # SOURCE: official submission time budget; tighter acceptance criteria require measurement.
    print(json.dumps({"busy_day_events": 400, "completed_simulated": 400, "seconds": elapsed}))
