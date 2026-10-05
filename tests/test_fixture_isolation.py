import asyncio
import time

import httpx

from eventdesk.config import Settings
from eventdesk.schemas import Event
from eventdesk.worker import Worker


def test_production_never_uses_embedded_fixture_materials(settings, store, model, monkeypatch):
    import eventdesk.worker as module
    monkeypatch.setattr(module, "allowed_material_url", lambda *args: asyncio.sleep(0))
    real_items = {"earnings-call-facts": ["Revenue declined and guidance cut."]}
    event = Event(id="delivery-isolation", event_id="event-isolation", event_type="EARNINGS_RELEASE",
        knowledge_cutoff="2026-01-01T00:00:00Z", information_url="https://fixture.invalid/official",
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}],
        fixture_materials={"items": [{"id": "earnings-call-facts", "content": ["Revenue increased guidance raised"]}]})
    store.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    production = Settings(settings.database_url, settings.model_path, settings.submissions, False,
                          frozenset({"fixture.invalid"}))
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json={"items": [{"id": "earnings-call-facts", "content": real_items["earnings-call-facts"]}]})
        return httpx.Response(201, json={"status": "fixture_accepted"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await Worker(production, store, model, client).process(store.claim(time.time()))
    asyncio.run(run())
    saved = store.public_event(event.event_id)
    assert saved["official_items"] == real_items
    assert saved["prediction"]["predictions"][0]["predicted_percentile"] == model.predict(real_items)
