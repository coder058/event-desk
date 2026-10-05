import asyncio
import json
import time

import httpx
import pytest

from eventdesk.llm import AnalysisResult
from eventdesk.schemas import Event
from eventdesk.worker import Worker


def test_slow_optional_ai_and_malformed_materials_cannot_block_predictions(settings, store, model, monkeypatch):
    import eventdesk.worker as module
    monkeypatch.setattr(module, "allowed_material_url", lambda *args: asyncio.sleep(0))
    production = type(settings)(settings.database_url, settings.model_path, settings.submissions,
                                False, frozenset({"fixture.invalid"}))
    # PLACEHOLDER: 24 synthetic events exercise more than two dispatcher batches; no market observation.
    for number in range(24):
        event = Event(id=f"dispatch-{number}", event_id=f"dispatch-{number}", event_type="EARNINGS_RELEASE",
            knowledge_cutoff="2026-01-01T00:00:00Z", information_url="https://fixture.invalid/" + str(number),
            focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
        store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    posts = []
    def handler(request):
        if request.method == "GET":
            facts = [42] if request.url.path == "/0" else ["Revenue increased."]
            return httpx.Response(200, json={"items": [{"id": "earnings-call-facts", "content": facts}]})
        posts.append(json.loads(request.content))
        return httpx.Response(201, json={"status": "fixture_accepted"})
    async def run():
        gate = asyncio.Event()
        started = asyncio.Event()
        class SlowShadow:
            async def analyze(self, items, deadline):
                started.set()
                await gate.wait()
                return AnalysisResult(None, None, None, 0, ({"status": "fixture_cloud_outage"},))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            worker = Worker(production, store, model, http)
            worker.router = SlowShadow()
            tasks = [asyncio.create_task(worker.dispatch()), asyncio.create_task(worker.shadow_loop())]
            try:
                # GUESS: bounded test timeout, not an asserted production latency.
                async with asyncio.timeout(10):
                    await started.wait()
                    while store.health()["states"] != {"api_accepted": 24}:
                        await asyncio.sleep(.01)
                assert not gate.is_set()  # Every prediction arrived while optional AI remained blocked.
                assert store.health()["states"] == {"api_accepted": 24}
                assert len(posts) == 24
                assert store.public_event("dispatch-0")["shadow_state"] is None
                assert store.public_event("dispatch-0")["fallback"] == "invalid_materials_or_model_output"
                malformed = next(payload for payload in posts if payload["event_id"] == "dispatch-0")
                assert malformed["predictions"][0]["predicted_percentile"] == model.training_mean
            finally:
                gate.set()
                for task in tasks:
                    task.cancel()
                for task in tasks:
                    with pytest.raises(asyncio.CancelledError):
                        await task
    asyncio.run(run())
