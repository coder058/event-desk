"""Optional real-provider smoke: isolated event book, mock official API, shared provider quotas.

Only a fixture key reaches the mock competition request. Only the free Gemini/Groq connections
are real. The result cannot establish market accuracy or official delivery.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from eventdesk.config import COMPETITION_ORIGIN, PREDICTION_BUDGET_SECONDS, Settings, Submission
from eventdesk.freeze import verify_freeze
from eventdesk.llm import Provider, Router, providers_from_env
from eventdesk.materials import input_hash
from eventdesk.model import LocalModel
from eventdesk.quotas import Quotas
from eventdesk.schemas import Event
from eventdesk.store import Store
from eventdesk.worker import Worker


async def exercise(*, book: Store, model: LocalModel, quotas: Quotas,
                   provider_http: httpx.AsyncClient, providers: tuple[Provider, ...], items: dict) -> dict:
    event = Event(id="shadow-provider-fictional-event", event_id="shadow-provider-fictional-event",
        event_type="EARNINGS_RELEASE", knowledge_cutoff=datetime.now(UTC),
        information_url=COMPETITION_ORIGIN+"/walkthrough-fixture-not-a-real-endpoint",
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "DEMO"}])
    # PLACEHOLDER: no owner competition credentials; this key reaches only the in-process mock transport.
    settings = Settings(str(book.engine.url), Path("unused-fixture-model-path"),
        {"s1": Submission("s1", "fixture-not-an-owner-key", "fixture-unused-signature")}, False,
        frozenset({"api.explainingmarkets.ai"}))
    mocked_posts = []
    def official_mock(request):
        if request.method == "GET" and str(request.url) == event.information_url:
            return httpx.Response(200, json={"items": [{"id": key, "content": value} for key, value in items.items()]})
        if request.method == "POST" and str(request.url) == COMPETITION_ORIGIN+"/predictions":
            assert request.headers["X-API-Key"] == "fixture-not-an-owner-key"
            mocked_posts.append(json.loads(request.content))
            return httpx.Response(201, json={"status": "mock_acceptance_not_competition"})
        raise AssertionError("Unexpected official mock request")
    book.receive("s1", event.id, event.model_dump_json().encode(), event, time.time())
    async with httpx.AsyncClient(transport=httpx.MockTransport(official_mock)) as official_http:
        worker = Worker(settings, book, model, official_http)
        worker.router = Router(quotas, provider_http, providers)
        worker.blend = None  # SOURCE: smoke only exercises the frozen post-submission lane.
        work = book.claim(time.time())
        assert work is not None
        await worker.process(work)
        before = book.public_event(event.event_id)
        assert before and before["state"] == "api_accepted" and before["shadow_state"] == "pending"
        before_payload = json.dumps(before["prediction"], sort_keys=True)
        task = asyncio.create_task(worker.shadow_loop())
        try:
            # SOURCE: official event budget bounds the entire synthetic run; no provider cooldown bypass.
            async with asyncio.timeout(PREDICTION_BUDGET_SECONDS):
                while True:
                    if task.done():
                        task.result()
                        raise AssertionError("Shadow loop stopped before a retained outcome")
                    after = book.public_event(event.event_id)
                    if after and after["shadow_state"] in {"validated", "unavailable", "failed", "expired"}:
                        break
                    # GUESS: fixture-only observation cadence, not a production latency target. # UNCALIBRATED GUESS
                    await asyncio.sleep(.05)
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    assert json.dumps(after["prediction"], sort_keys=True) == before_payload
    assert len(mocked_posts) == 1 and after["inputs_hash"] == input_hash(items)
    return {"schema_version": "eventdesk-shadow-smoke-v1", "fixture_only": True,
        "checked_at": datetime.now(UTC).isoformat(), "model_sha256": model.sha256,
        "inputs_sha256": after["inputs_hash"], "external_official_requests": 0,
        "mock_official_posts": len(mocked_posts), "prediction_unchanged": True,
        "shadow_state": after["shadow_state"], "analysis_trace": after["analysis_trace"],
        "limits": "Fictional inputs, disposable SQLite event book, mock competition acceptance. Real provider calls use shared PostgreSQL quotas. No live event, score or profitability."}


async def main() -> None:
    if os.getenv("EVENTDESK_ALLOW_REAL_PROVIDER_SMOKE") != "true":
        raise ValueError("Explicit real-provider smoke flag required")
    shared = Store(os.environ["DATABASE_URL"])
    if shared.engine.dialect.name != "postgresql":
        raise ValueError("Real smoke requires the shared PostgreSQL quota ledger")
    demo = json.loads(Path("reports/walkthrough.json").read_text(encoding="utf-8"))
    if demo.get("fixture_only") is not True or demo["record"]["state"] != "simulated":
        raise ValueError("Expected retained fictional walkthrough")
    model = LocalModel(Path(os.environ["EVENTDESK_MODEL_PATH"]), expected_sha256=demo["record"]["model_hash"])
    providers = providers_from_env()
    assert providers
    verify_freeze(Path("competition-config.json"), model, hybrid_enabled=False,
                  post_submission_evidence_enabled=True,
                  provider_models={provider.name: provider.model for provider in providers})
    provider_requests = []
    async def counted(request):
        assert request.url.host in {"generativelanguage.googleapis.com", "api.groq.com"}
        provider_requests.append(request.url.host)  # Never retain query strings/headers/keys.
    try:
        with tempfile.TemporaryDirectory(prefix="eventdesk-shadow-smoke-") as temporary:
            book = Store("sqlite:///"+str(Path(temporary)/"fictional.sqlite"))
            book.initialize_fixture()
            try:
                async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                    event_hooks={"request": [counted]}) as http:
                    proof = await exercise(book=book, model=model, quotas=Quotas(shared),
                        provider_http=http, providers=providers, items=demo["record"]["official_items"])
            finally:
                book.engine.dispose()
        proof["actual_provider_requests"] = len(provider_requests)
        print(json.dumps(proof, allow_nan=False))
    finally:
        shared.engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        print(json.dumps({"failed": True, "error_type": type(error).__name__, "details_withheld": True}))
        raise SystemExit(1) from None
