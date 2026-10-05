import asyncio
import json
import time
from dataclasses import replace

import httpx
import pytest

from eventdesk.config import SUBMISSION_RESERVE_SECONDS
from eventdesk.schemas import Event
from eventdesk.worker import Worker


def test_reserved_queue_drains_without_new_material_requests(settings, store, model, monkeypatch):
    import eventdesk.worker as module
    monkeypatch.setattr(module, "allowed_material_url", lambda *args: asyncio.sleep(0))
    production = type(settings)(settings.database_url, settings.model_path, settings.submissions,
                                False, frozenset({"fixture.invalid"}))
    # PLACEHOLDER: clock places synthetic backlog inside the mission's 30-second submission reserve.
    now = time.time()
    event = Event(id="reserved", event_id="reserved", event_type="EARNINGS_RELEASE",
        knowledge_cutoff="2026-01-01T00:00:00Z", information_url="https://fixture.invalid/materials",
        prediction_deadline=now+SUBMISSION_RESERVE_SECONDS,
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, now)
    posts = []
    def handler(request):
        assert request.method == "POST"
        posts.append(json.loads(request.content))
        return httpx.Response(201, json={"status": "fixture_accepted_not_official"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            await Worker(production, store, model, http).process(store.claim(time.time()))
    asyncio.run(run())
    record = store.public_event(event.event_id)
    assert record["fallback"] == "materials_skipped_deadline_reserve"
    assert record["local_trace"]["kind"] == "fitted_training_mean"
    assert posts[0]["predictions"][0]["predicted_percentile"] == model.training_mean
    assert store.scoreboard()["material_fallbacks"] == 1


@pytest.mark.parametrize("stall", ["dns", "body"])
def test_dns_and_body_stalls_share_the_material_phase_budget(settings, store, model, monkeypatch, stall):
    import eventdesk.worker as module
    # GUESS: shortened fault-test budget; production retains the required 30-second reserve. # UNCALIBRATED GUESS
    monkeypatch.setattr(module, "SUBMISSION_RESERVE_SECONDS", 299.95)
    async def dns(*args):
        if stall == "dns":
            await asyncio.Event().wait()
    monkeypatch.setattr(module, "allowed_material_url", dns)
    production = type(settings)(settings.database_url, settings.model_path, settings.submissions,
                                False, frozenset({"fixture.invalid"}))
    event = Event(id=stall, event_id=stall, event_type="EARNINGS_RELEASE",
        knowledge_cutoff="2026-01-01T00:00:00Z", information_url="https://fixture.invalid/materials",
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    class StalledBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.Event().wait()
            yield b"never"
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, stream=StalledBody())
        return httpx.Response(201, json={"status": "fixture_accepted_not_official"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            # GUESS: bounded test watchdog, not an asserted production latency. # UNCALIBRATED GUESS
            async with asyncio.timeout(2):
                work = store.claim(time.time())
                # PLACEHOLDER: start the injected 50 ms budget after fixture/client/database setup.
                work = replace(work, deadline=time.time()+module.SUBMISSION_RESERVE_SECONDS+.05)
                await Worker(production, store, model, http).process(work)
    asyncio.run(run())
    record = store.public_event(stall)
    assert record["state"] == "api_accepted"
    assert record["fallback"] == "materials_unavailable"
    assert record["local_trace"]["prediction"] == model.training_mean
