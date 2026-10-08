import asyncio
import json
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from test_delivery import signed

from eventdesk.api import create_app
from eventdesk.schemas import Event
from eventdesk.worker import Worker


@pytest.mark.parametrize("include_null_cutoff", [False, True])
def test_official_non_test_shape_without_cutoff_receives_and_submits(
    settings, store, model, monkeypatch, include_null_cutoff,
):
    # SOURCE: starter-modal/src/explaining_markets/event_utils.py's documented
    # verified payload omits knowledge_cutoff; its README places it on the calendar.
    # FAQ permits the delivered official materials even after the calendar cutoff.
    # PLACEHOLDER: synthetic identities, materials and API responses; no official POST.
    payload = {
        "id": "contract-delivery", "event_id": "contract-event",
        "event_type": "EARNINGS_RELEASE", "timing_category": "SCHEDULED",
        "event_datetime": datetime.now(UTC).isoformat(),
        "focal_assets": [{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}],
        "information_url": "https://fixture.invalid/official-materials",
        # SOURCE: existing official five-minute prediction budget, not a calibrated constant.
        "prediction_deadline": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    }
    if include_null_cutoff:
        payload["knowledge_cutoff"] = None
    raw = json.dumps(payload).encode()
    production = replace(settings, fixture_mode=False, material_hosts=frozenset({"fixture.invalid"}))
    client = TestClient(create_app(production, store))
    headers = signed(raw, payload["id"])
    assert client.post("/competition/webhook", content=raw, headers=headers).status_code == 200
    assert client.post("/competition/webhook", content=raw, headers=headers).status_code == 200
    assert store.health()["states"] == {"pending": 1}
    requests = []
    items = {"earnings-call-facts": ["Revenue increased and guidance raised."]}

    async def fixture_dns(*args):
        return None

    monkeypatch.setattr("eventdesk.worker.allowed_material_url", fixture_dns)
    monkeypatch.delenv("EVENTDESK_LLM_ENABLED", raising=False)

    def handler(request):
        requests.append(request)
        if request.method == "GET":
            assert str(request.url) == payload["information_url"]
            return httpx.Response(200, json={"items": [
                {"id": "earnings-call-facts", "kind": "facts", "content": items["earnings-call-facts"]},
                {"id": "outcome", "kind": "stats", "content": {"future_return": "excluded"}},
            ]})
        assert request.method == "POST"
        return httpx.Response(201, json={"status": "fixture_accepted_not_official"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as http:
            await Worker(production, store, model, http).process(store.claim(time.time()))

    asyncio.run(run())
    record = store.public_event(payload["event_id"])
    assert record["state"] == "api_accepted"
    assert record["knowledge_cutoff"] is None
    assert record["official_items"] == items
    assert record["local_trace"]["kind"] != "fitted_training_mean"
    assert record["prediction"]["predictions"][0]["predicted_percentile"] == model.predict(items)
    assert json.loads(requests[-1].content) == record["prediction"]
    assert [r.method for r in requests] == ["GET", "POST"]
    assert store.scoreboard()["api_accepted"] == 1


def test_missing_cutoff_does_not_allow_supplemental_or_private_materials(settings, store, model, monkeypatch):
    # PLACEHOLDER: blocked private HTTP URL, never contacted; mocked submission only.
    event = Event(id="blocked-material", event_id="blocked-material", event_type="EARNINGS_RELEASE",
        information_url="http://127.0.0.1/private", focal_assets=[
            {"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    production = replace(settings, fixture_mode=False)
    raw = event.model_dump_json().encode()
    assert TestClient(create_app(production, store)).post(
        "/competition/webhook", content=raw, headers=signed(raw, event.id)).status_code == 200
    monkeypatch.delenv("EVENTDESK_LLM_ENABLED", raising=False)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        return httpx.Response(201, json={"status": "fixture_accepted_not_official"})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), trust_env=False) as http:
            await Worker(production, store, model, http).process(store.claim(time.time()))

    asyncio.run(run())
    record = store.public_event(event.event_id)
    assert record["state"] == "api_accepted"
    assert record["fallback"] == "materials_unavailable"
    assert record["official_items"] == {}
    assert record["local_trace"]["kind"] == "fitted_training_mean"
    assert len(requests) == 1
