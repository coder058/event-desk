"""Actual worker/PG fault drill with a transport that cannot reach any network."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

import httpx
from sqlalchemy.engine import make_url

import eventdesk.worker as worker_module
from eventdesk.config import PREDICTION_BUDGET_SECONDS, SUBMISSION_RESERVE_SECONDS, Settings, Submission
from eventdesk.model import LocalModel
from eventdesk.schemas import Event
from eventdesk.store import Store
from eventdesk.worker import Worker

# SOURCE: mission's requested 400-event infrastructure busy-day drill.
EVENTS = 400


async def main(database: str, mode: str, events: int = EVENTS) -> None:
    if not re.fullmatch(r"eventdesk_fault_\d+", database) or mode not in ("reserve", "source_outage"):
        raise ValueError("Only a separately created fault-drill database is allowed")
    # GUESS: cap operator fault workloads at 1,000 to bound existing VPS resource use. # UNCALIBRATED GUESS
    if not 1 <= events <= 1000:
        raise ValueError("Fault workload outside operational ceiling")
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or url.database == database:
        raise ValueError("Source must be production PG URL; drill target must be different")
    # Never emit the URL/password. Isolated credentials and a mock transport replace all HTTP.
    store = Store(url.set(database=database).render_as_string(hide_password=False))
    store.initialize_fixture()
    os.environ["EVENTDESK_LLM_ENABLED"] = "false"
    settings = Settings(str(store.engine.url), Path("/models/local-model.joblib"),
        {"s1": Submission("s1", "fixture-only", "fixture-only")}, False, frozenset({"fixture.invalid"}))
    model = LocalModel(settings.model_path)
    calls: Counter[str] = Counter()
    replies = []
    original_dns = worker_module.allowed_material_url
    async def no_dns(url, hosts):
        if not url.startswith("https://fixture.invalid/") or hosts != frozenset({"fixture.invalid"}):
            raise AssertionError("Fault drill received an unexpected material route")
    worker_module.allowed_material_url = no_dns
    async def handler(request):
        if request.method == "GET" and request.url.host == "fixture.invalid":
            calls["stalled_material_gets"] += 1
            await asyncio.Event().wait()
            raise AssertionError("Injected material stall unexpectedly released")
        if request.method == "POST" and str(request.url) == "https://api.explainingmarkets.ai/v1/predictions":
            calls["simulated_submission_responses"] += 1
            replies.append(json.loads(request.content))
            return httpx.Response(201, json={"status": "fixture_accepted"})
        raise AssertionError("Unexpected network request in isolated fault drill")
    seeded_at = time.time()
    received_at = (seeded_at-(PREDICTION_BUDGET_SECONDS-SUBMISSION_RESERVE_SECONDS)
                   if mode == "reserve" else seeded_at)
    try:
        for index in range(events):
            event = Event(id=f"fault-{index}", event_id=f"fault-{index}", event_type="EARNINGS_RELEASE",
                knowledge_cutoff="2026-01-01T00:00:00Z", information_url=f"https://fixture.invalid/{index}",
                focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
            store.receive("s1", event.id, event.model_dump_json().encode(), event, received_at)
        seeded_seconds = time.time()-seeded_at
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            worker = Worker(settings, store, model, http)
            task = asyncio.create_task(worker.dispatch())
            try:
                # SOURCE: official five-minute budget, less the deliberately elapsed seed age.
                async with asyncio.timeout(received_at+PREDICTION_BUDGET_SECONDS-time.time()):
                    while store.health()["states"] != {"api_accepted": events}:
                        # GUESS: bounded fault-drill completion polling only.
                        # UNCALIBRATED GUESS
                        await asyncio.sleep(.05)
            finally:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        assert len(replies) == events
        assert all(payload["predictions"][0]["predicted_percentile"] == model.training_mean for payload in replies)
        from sqlalchemy import func, select
        from sqlalchemy.orm import Session

        from eventdesk.store import Job
        with Session(store.engine) as session:
            fallbacks = dict(session.execute(select(Job.fallback, func.count()).group_by(Job.fallback)).all())
        print(json.dumps({"kind": "isolated_pg_worker_mock_transport_fault_drill", "mode": mode,
            "events": events, "elapsed_seconds": time.time()-seeded_at, "seed_seconds": seeded_seconds,
            "deadline_from_seed_seconds": received_at+PREDICTION_BUDGET_SECONDS-seeded_at,
            "completed_mock_responses": len(replies), "transport_calls": dict(calls), "fallbacks": fallbacks,
            "model_sha256": model.sha256, "external_network_requests": 0,
            "limits": "Actual PG/worker with synthetic events and stalled mock GETs; POSTs are simulated, "
                      "not official submissions. No live network/ACK latency or model accuracy is established."}))
    except Exception as exc:
        print(json.dumps({"kind": "isolated_pg_worker_mock_transport_fault_drill", "mode": mode,
            "events": events, "failure_type": type(exc).__name__, "states": store.health()["states"],
            "transport_calls": dict(calls), "elapsed_seconds": time.time()-seeded_at,
            "external_network_requests": 0, "limits": "Failed isolated mock-transport drill; not official submissions"}))
        raise
    finally:
        worker_module.allowed_material_url = original_dns
        store.engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else EVENTS))
