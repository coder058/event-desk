import asyncio
import json
import time
from pathlib import Path

import httpx
import joblib
import pytest

from eventdesk.blend import BlendModel
from eventdesk.config import Settings
from eventdesk.llm import AnalysisResult
from eventdesk.schemas import Event, LLMAnalysis
from eventdesk.worker import Worker


def test_unapproved_fitted_artifact_never_used(tmp_path):
    path = tmp_path / "unapproved.joblib"
    joblib.dump({"schema_version": "eventdesk-blend-v1", "deployment_approved": False}, path)
    with pytest.raises(ValueError, match="approval"):
        BlendModel(path)


def test_shadow_cannot_delay_local_submission_or_change_payload(settings, store, model, monkeypatch):
    import eventdesk.worker as module
    monkeypatch.setattr(module, "allowed_material_url", lambda *args: asyncio.sleep(0))
    source = {"items": [{"id": "earnings-call-facts", "content": ["Revenue increased."]}]}
    e = Event(id="delivery-shadow", event_id="event-shadow", event_type="EARNINGS_RELEASE",
              knowledge_cutoff="2026-01-01T00:00:00Z", information_url="https://fixture.invalid/materials",
              focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", e.id, e.model_dump_json().encode(), e, time.time())
    prod = Settings(settings.database_url, Path("fixture"), settings.submissions, False,
                    frozenset({"fixture.invalid"}))
    class ShadowRouter:
        async def analyze(self, items, deadline):
            # Simulates an unavailable/slow cloud: local submission must already have completed.
            assert len(posted) == 1
            assert store.public_event(e.event_id)["state"] == "api_accepted"
            analysis = LLMAnalysis(beat_vs_buyside_bar=1, guidance_change=0, tone=0, new_risks=0,
                surprise_vs_preview=0, confidence=.5,
                evidence=[{"item_id": "earnings-call-facts", "quote": "Revenue increased."}])
            return AnalysisResult(analysis, "fixture-provider", "fixture-model", 1, ())
    posted = []
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=source)
        posted.append(json.loads(request.content))
        # The durable outbox exists before POST, with optional shadow work queued atomically.
        saved = store.public_event(e.event_id)
        assert saved["analysis_trace"] is None
        assert saved["shadow_state"] == "pending"
        assert saved["prediction"] == posted[-1]
        return httpx.Response(201, json={"status": "fixture_accepted"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            worker = Worker(prod, store, model, http)
            worker.router = ShadowRouter()
            await worker.process(store.claim(time.time()))
            task = asyncio.create_task(worker.shadow_loop())
            for _ in range(100):  # PLACEHOLDER: bounded async fixture polling, not a market rule.
                if store.public_event(e.event_id)["shadow_state"] == "validated":
                    break
                await asyncio.sleep(.01)
            else:
                raise AssertionError("Shadow evidence did not complete")
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(run())
    expected = model.predict({"earnings-call-facts": ["Revenue increased."]})
    assert posted[0]["predictions"][0]["predicted_percentile"] == expected
    saved = store.public_event(e.event_id)
    assert saved["fallback"] == "llm_shadow_deferred"
    assert saved["prediction"] == posted[0]
    assert saved["analysis_trace"]["affects_prediction"] is False
    assert saved["analysis_trace"]["timing"] == "after_local_submission"


def test_shadow_queue_restarts_without_revising_outbox(settings, store):
    from eventdesk.store import ConflictError, Store
    e = Event(id="delivery-restart", event_id="event-restart", event_type="EARNINGS_RELEASE",
              knowledge_cutoff="2026-01-01T00:00:00Z",
              focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", e.id, e.model_dump_json().encode(), e, time.time())
    work = store.claim(time.time())
    payload = {"event_id": e.event_id, "predictions": [{"identifier_value": "FIXTURE", "predicted_percentile": .4}]}
    store.persist_prediction(work.id, payload, {"earnings-call-facts": ["Revenue increased."]},
                             "fixture-model", "llm_shadow_deferred", defer_shadow=True)
    assert store.claim_shadow(time.time()) is None  # Cannot analyze before API acceptance.
    store.finish(work.id, {"status": "fixture_accepted"}, "api_accepted", time.time())
    first = store.claim_shadow(time.time())
    assert first is not None
    assert store.claim_shadow(time.time()) is None
    restarted = Store(settings.database_url)
    restarted.recover()
    second = restarted.claim_shadow(time.time())
    assert first == second
    with pytest.raises(ConflictError, match="cannot change"):
        restarted.finish_shadow(second.id, {"affects_prediction": True}, "validated")
    restarted.finish_shadow(second.id, {"affects_prediction": False}, "unavailable")
    restarted.finish_shadow(second.id, {"affects_prediction": False}, "unavailable")
    with pytest.raises(ConflictError, match="immutable"):
        restarted.finish_shadow(second.id, {"affects_prediction": False, "retrospective_change": True}, "validated")
    assert restarted.public_event(e.event_id)["prediction"] == payload
    assert restarted.claim_shadow(time.time()) is None
