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


def test_shadow_evidence_and_local_outbox_commit_together(settings, store, model, monkeypatch):
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
            analysis = LLMAnalysis(beat_vs_buyside_bar=1, guidance_change=0, tone=0, new_risks=0,
                surprise_vs_preview=0, confidence=.5,
                evidence=[{"item_id": "earnings-call-facts", "quote": "Revenue increased."}])
            return AnalysisResult(analysis, "fixture-provider", "fixture-model", 1, ())
    posted = []
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=source)
        posted.append(json.loads(request.content))
        # Ensure evidence and outbox both exist before any external submission.
        saved = store.public_event(e.event_id)
        assert saved["analysis_trace"]["analysis"] is not None
        assert saved["prediction"] == posted[-1]
        assert saved["analysis_trace"]["affects_prediction"] is False
        return httpx.Response(201, json={"status": "fixture_accepted"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            worker = Worker(prod, store, model, http)
            worker.router = ShadowRouter()
            await worker.process(store.claim(time.time()))
    asyncio.run(run())
    expected = model.predict({"earnings-call-facts": ["Revenue increased."]})
    assert posted[0]["predictions"][0]["predicted_percentile"] == expected
    assert store.public_event(e.event_id)["fallback"] == "llm_shadow_no_approved_blend"
