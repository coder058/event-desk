"""Recoverable local-first worker. No strategy can alter a persisted prediction."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from eventdesk.blend import BlendModel
from eventdesk.config import COMPETITION_ORIGIN, Settings
from eventdesk.llm import PROMPT_HASH, Router, prompt_materials, providers_from_env
from eventdesk.materials import input_hash, select_items
from eventdesk.model import LocalModel
from eventdesk.quotas import Quotas
from eventdesk.schemas import Prediction, SubmissionPayload
from eventdesk.store import Store, Work

LOG = logging.getLogger("eventdesk.worker")


async def allowed_material_url(url: str, hosts: frozenset[str]) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password:
        raise ValueError("Material host not authorized")
    if parsed.port not in (None, 443):  # SOURCE: HTTPS standard port; no arbitrary services.
        raise ValueError("Nonstandard material port")
    resolved = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443)
    if not resolved or any(not ipaddress.ip_address(item[4][0]).is_global for item in resolved):
        raise ValueError("Material destination is not public")


class Worker:
    def __init__(self, settings: Settings, store: Store, model: LocalModel,
                 http: httpx.AsyncClient) -> None:
        self.settings, self.store, self.model, self.http = settings, store, model, http
        self.router: Router | None = None
        self.blend: BlendModel | None = None
        if os.getenv("EVENTDESK_LLM_ENABLED", "false").lower() == "true" and not settings.fixture_mode:
            self.router = Router(Quotas(store), http, providers_from_env())
            blend_path = os.getenv("EVENTDESK_BLEND_PATH")
            if blend_path:
                self.blend = BlendModel(Path(blend_path))

    async def process(self, work: Work) -> None:
        payload = work.payload
        if payload is None:
            items: dict[str, Any] = {}
            fallback: str | None = None
            method = "local"
            selected_model_hash = self.model.sha256
            trace: dict[str, Any] | None = None
            if work.event.event_type == "TEST":
                # SOURCE: official starter neutral prediction for TEST (never scored).
                value = 0.5
                fallback = "official_test_event"
            else:
                try:
                    if self.settings.fixture_mode:
                        supplied_fixture = (work.event.model_extra or {}).get("fixture_materials")
                        items = select_items(supplied_fixture) if isinstance(supplied_fixture, dict) else {
                            "earnings-call-facts": ["Revenue increased and guidance was maintained."]}
                    elif work.event.information_url:
                        await allowed_material_url(work.event.information_url, self.settings.material_hosts)
                        # SOURCE: starter materials timeout 15 seconds; bounded by actual remaining deadline.
                        response = await self.http.get(work.event.information_url,
                                                       timeout=max(0.1, min(15, work.deadline - time.time())))
                        response.raise_for_status()
                        items = select_items(response.json())
                    else:
                        fallback = "materials_missing_url"
                except (httpx.HTTPError, ValueError, OSError):
                    fallback = "materials_unavailable"
                value = await asyncio.to_thread(self.model.predict, items)
                if self.router and items and fallback is None:
                    local_value = value
                    result = await self.router.analyze(items, work.deadline)
                    trace = {"prompt_hash": PROMPT_HASH,
                        "llm_inputs_hash": input_hash(prompt_materials(items)),
                        "provider": result.provider, "model": result.model,
                        "latency_ms": result.latency_ms, "attempts": list(result.attempts),
                        "analysis": result.analysis.model_dump() if result.analysis else None,
                        "local_prediction": local_value, "affects_prediction": False}
                    if result.analysis and self.blend and result.provider and result.model:
                        try:
                            value = self.blend.predict(local_value, result.analysis, prompt_hash=PROMPT_HASH,
                                                       provider=result.provider, provider_model=result.model)
                            method = "fitted_blend"
                            selected_model_hash = self.model.sha256 + ":" + self.blend.sha256
                            trace["affects_prediction"] = True
                            trace["blend_hash"] = self.blend.sha256
                        except ValueError:
                            fallback = "blend_provenance_mismatch"
                    elif result.analysis:
                        fallback = "llm_shadow_no_approved_blend"
                    else:
                        fallback = "llm_unavailable"
                fallback = fallback or ("llm_not_enabled" if not self.router else None)
            # Current official earnings events have event-level materials; same fitted model applied to each
            # asset until an asset-specific model is actually trained and evaluated.
            payload = SubmissionPayload(event_id=work.event.event_id,
                                        predictions=[Prediction(identifier_value=asset.identifier_value,
                                                                predicted_percentile=value)
                                                     for asset in work.event.focal_assets]).model_dump(mode="json")
            await asyncio.to_thread(self.store.persist_prediction, work.id, payload, items,
                                    selected_model_hash, fallback, method, trace)
        remaining = work.deadline - time.time()
        if remaining <= 0:
            await asyncio.to_thread(self.store.retry, work.id, "deadline_expired", 0, time.time())
            return
        if self.settings.fixture_mode:
            await asyncio.to_thread(self.store.finish, work.id,
                                    {"status": "fixture_simulation_not_competition"}, "simulated", time.time())
            return
        try:
            response = await self.http.post(COMPETITION_ORIGIN + "/predictions", json=payload,
                                           headers={"X-API-Key": self.settings.submissions[work.slot].api_key},
                                           timeout=min(15, remaining))
            if response.status_code == 201:
                body = response.json()
                await asyncio.to_thread(self.store.finish, work.id, body, "api_accepted", time.time())
                LOG.info("submission event=%s slot=%s state=api_accepted", work.event.event_id, work.slot)
            elif response.status_code in (401, 403, 409, 422):
                await asyncio.to_thread(self.store.finish, work.id,
                                        {"status": "rejected", "http_status": response.status_code},
                                        "rejected", time.time())
                LOG.error("submission event=%s rejected_http=%s", work.event.event_id, response.status_code)
            else:
                # GUESS: two-second retry delay for transport/server errors; always identical stored payload.
                await asyncio.to_thread(self.store.retry, work.id, "submission_http_" + str(response.status_code),
                                        2, time.time())
        except (httpx.HTTPError, ValueError):
            # An uncertain POST may have reached the server. Reusing the outbox prevents a revised prediction.
            await asyncio.to_thread(self.store.retry, work.id, "submission_transport_uncertain", 2, time.time())

    async def loop(self) -> None:
        while True:
            work = await asyncio.to_thread(self.store.claim, time.time())
            if work is None:
                # GUESS: bounded polling interval; latency must be measured under the busy-day test.
                await asyncio.sleep(0.25)
                continue
            try:
                await self.process(work)
            except Exception as exc:
                # Never print exception text: SDK exceptions can include signed URLs or credentials.
                LOG.error("worker_failure event=%s exception_type=%s", work.event.event_id, type(exc).__name__)
                await asyncio.to_thread(self.store.retry, work.id, "worker_" + type(exc).__name__, 2, time.time())


async def run() -> None:
    settings = Settings.from_env()
    store = Store(settings.database_url)
    model = LocalModel(settings.model_path)
    if model.artifact.get("fixture_only") and not settings.fixture_mode:
        raise RuntimeError("Refusing synthetic fixture model in production")
    await asyncio.to_thread(store.recover)
    LOG.info("worker_started model_hash=%s fixture=%s", model.sha256, settings.fixture_mode)
    async with httpx.AsyncClient(follow_redirects=False) as http:
        worker = Worker(settings, store, model, http)
        # GUESS: eight I/O workers sharing one fitted artifact; evaluate load rather than claim capacity.
        await asyncio.gather(*(worker.loop() for _ in range(8)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Signed material query strings and auth-bearing SDK exceptions must not enter transport logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    asyncio.run(run())
