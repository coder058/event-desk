import asyncio
import importlib.util
from pathlib import Path

import httpx

from eventdesk.llm import Provider
from eventdesk.quotas import Limits, Quotas


def test_shadow_provider_smoke_runs_actual_worker_and_preserves_immutable_forecast(settings, store, model, monkeypatch):
    import eventdesk.worker as worker_module
    monkeypatch.setattr(worker_module, "allowed_material_url", lambda *args: asyncio.sleep(0))
    spec = importlib.util.spec_from_file_location("shadow_smoke", Path("research/shadow_smoke.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    def provider(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content":
            '{"beat_vs_buyside_bar":0,"guidance_change":0,"tone":0,"new_risks":0,'
            '"surprise_vs_preview":0,"confidence":0.5,"evidence":'
            '[{"item_id":"earnings-call-facts","quote":"Revenue increased."}]}'}}],
            "usage": {"total_tokens": 10}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as http:
            # PLACEHOLDER: synthetic provider/output/budget exercises wiring, not actual free-tier capacity.
            return await module.exercise(book=store, model=model, quotas=Quotas(store), provider_http=http,
                providers=(Provider("groq", "fixture-model", "fixture-key", Limits(10, 10, 100000, 100000)),),
                items={"earnings-call-facts": ["Revenue increased."]})
    proof = asyncio.run(run())
    assert proof["external_official_requests"] == 0 and proof["mock_official_posts"] == 1
    assert proof["shadow_state"] == "validated" and proof["prediction_unchanged"] is True
    assert proof["analysis_trace"]["affects_prediction"] is False
    assert proof["analysis_trace"]["timing"] == "after_local_submission"
    assert len(calls) == 1
