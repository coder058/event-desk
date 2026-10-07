"""Recoverable local-first worker. No strategy can alter a persisted prediction."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import socket
import time
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from opentelemetry.trace import Span

from eventdesk.blend import BlendModel
from eventdesk.config import COMPETITION_ORIGIN, SUBMISSION_RESERVE_SECONDS, Settings
from eventdesk.freeze import CompetitionFreeze, verify_freeze
from eventdesk.http_policy import retry_delay, submit_bounded
from eventdesk.llm import PROMPT_HASH, Router, prompt_materials, providers_from_env
from eventdesk.materials import input_hash, select_items
from eventdesk.model import LocalModel
from eventdesk.quotas import Quotas
from eventdesk.schemas import Prediction, SubmissionPayload
from eventdesk.store import Store, Work
from eventdesk.telemetry import Telemetry

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
                 http: httpx.AsyncClient, *, telemetry: Telemetry | None = None) -> None:
        self.settings, self.store, self.model, self.http = settings, store, model, http
        self.router: Router | None = None
        self.blend: BlendModel | None = None
        self.configuration_hash: str | None = None
        self.telemetry = telemetry
        if os.getenv("EVENTDESK_LLM_ENABLED", "false").lower() == "true" and not settings.fixture_mode:
            self.router = Router(Quotas(store), http, providers_from_env())
            blend_path = os.getenv("EVENTDESK_BLEND_PATH")
            if blend_path:
                self.blend = BlendModel(Path(blend_path))

    def stage(self, name: str) -> AbstractContextManager[Span | None]:
        return self.telemetry.stage(name) if self.telemetry else nullcontext(None)

    async def process(self, work: Work) -> None:
        payload = work.payload
        if payload is None:
            items: dict[str, Any] = {}
            fallback: str | None = None
            method = "local"
            selected_model_hash = self.model.sha256
            trace: dict[str, Any] | None = None
            local_trace: dict[str, Any] | None = None
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
                        # SOURCE: mission's >=30-second submission reserve, also applied to DNS/body reads.
                        budget = work.deadline - time.time() - SUBMISSION_RESERVE_SECONDS
                        if budget <= 0:
                            fallback = "materials_skipped_deadline_reserve"
                        else:
                            # SOURCE: official starter's 15-second materials timeout; reserve bounds the whole phase.
                            with self.stage("eventdesk.materials"):
                                async with asyncio.timeout(min(15, budget)):
                                    await allowed_material_url(work.event.information_url, self.settings.material_hosts)
                                    async with self.http.stream("GET", work.event.information_url,
                                                                timeout=min(15, budget)) as response:
                                        response.raise_for_status()
                                        raw = bytearray()
                                        async for chunk in response.aiter_bytes():
                                            raw.extend(chunk)
                                            # GUESS: 16 MiB ceiling for official materials; not a model threshold. # UNCALIBRATED GUESS
                                            if len(raw) > 16 * 1024 * 1024:
                                                raise ValueError("Material body exceeds memory ceiling")
                                        bundle = json.loads(raw)
                                        # SOURCE: strict JSON numeric boundary; invalid material uses fitted fallback.
                                        json.dumps(bundle, allow_nan=False)
                                        items = select_items(bundle)
                    else:
                        fallback = "materials_missing_url"
                except (httpx.HTTPError, ValueError, OSError, TimeoutError):
                    fallback = "materials_unavailable"
                try:
                    with self.stage("eventdesk.local_inference"):
                        value = await asyncio.to_thread(self.model.predict, items)
                except (ValueError, TypeError, KeyError, IndexError):
                    # SOURCE: already-fitted target mean, not an invented fallback prediction.
                    value = self.model.training_mean
                    local_trace = {"kind": "fitted_training_mean", "prediction": value,
                                   "limits": "Invalid material or model output; no valid textual inference"}
                    fallback = "invalid_materials_or_model_output"
                    LOG.error("local_inference_fallback event=%s", work.event.event_id)
                if local_trace is None:
                    try:
                        local_trace = await asyncio.to_thread(self.model.explain, items)
                    except (ValueError, TypeError, KeyError, IndexError):
                        # Optional presentation cannot change a successfully computed forecast.
                        local_trace = {"kind": "explanation_unavailable", "prediction": value}
                        LOG.error("local_explanation_unavailable event=%s", work.event.event_id)
                if fallback is None and local_trace.get("kind") == "fitted_training_mean":
                    fallback = "official_facts_missing"
                if self.router and self.blend and items and fallback is None:
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
                if fallback is None:
                    fallback = "llm_not_enabled" if not self.router else (
                        "llm_shadow_deferred" if self.blend is None else None)
            # Current official earnings events have event-level materials; same fitted model applied to each
            # asset until an asset-specific model is actually trained and evaluated.
            payload = SubmissionPayload(event_id=work.event.event_id,
                                        predictions=[Prediction(identifier_value=asset.identifier_value,
                                                                predicted_percentile=value)
                                                     for asset in work.event.focal_assets]).model_dump(mode="json")
            await asyncio.to_thread(self.store.persist_prediction, work.id, payload, items,
                                    selected_model_hash, fallback, method, trace,
                                    bool(self.router and not self.blend and items and
                                         fallback == "llm_shadow_deferred" and
                                         work.event.event_type != "TEST"), local_trace, self.configuration_hash)
        remaining = work.deadline - time.time()
        if remaining <= 0:
            await asyncio.to_thread(self.store.retry, work.id, "deadline_expired", 0, time.time())
            return
        if self.settings.fixture_mode:
            await asyncio.to_thread(self.store.finish, work.id,
                                    {"status": "fixture_simulation_not_competition"}, "simulated", time.time())
            return
        try:
            with self.stage("eventdesk.submit") as span:
                receipt = await submit_bounded(self.http, COMPETITION_ORIGIN + "/predictions", payload=payload,
                    headers={"X-API-Key": self.settings.submissions[work.slot].api_key}, remaining=remaining)
                if span:
                    span.set_attribute("http.response.status_code", receipt.http_status)
            if receipt.http_status == 201:
                body = receipt.body
                await asyncio.to_thread(self.store.finish, work.id, body, "api_accepted", time.time())
                LOG.info("submission event=%s slot=%s state=api_accepted", work.event.event_id, work.slot)
            elif receipt.http_status in (401, 403, 409, 422):
                await asyncio.to_thread(self.store.finish, work.id,
                                        {"status": "rejected", "http_status": receipt.http_status},
                                        "rejected", time.time())
                LOG.error("submission event=%s rejected_http=%s", work.event.event_id, receipt.http_status)
            else:
                now = time.time()
                # SOURCE: honor server Retry-After (RFC 9110); the durable queue expires delays beyond the deadline.
                await asyncio.to_thread(self.store.retry, work.id, "submission_http_" + str(receipt.http_status),
                                        retry_delay(receipt.retry_after, now), now)
        except (httpx.HTTPError, OSError, ValueError, TimeoutError):
            # An uncertain POST may have reached the server. Reusing the outbox prevents a revised prediction.
            now = time.time()
            await asyncio.to_thread(self.store.retry, work.id, "submission_transport_uncertain",
                                    retry_delay(None, now), now)

    async def shadow_loop(self) -> None:
        """One optional evidence lane; never shares the deadline-critical worker pool."""
        if self.router is None or self.blend is not None:
            return
        while True:
            work = await asyncio.to_thread(self.store.claim_shadow, time.time())
            if work is None:
                # GUESS: same bounded queue polling as receipt processing; not market timing. # UNCALIBRATED GUESS
                await asyncio.sleep(0.25)
                continue
            try:
                result = await self.router.analyze(work.items, work.deadline)
                trace: dict[str, Any] = {"prompt_hash": PROMPT_HASH,
                    "llm_inputs_hash": input_hash(prompt_materials(work.items)),
                    "provider": result.provider, "model": result.model,
                    "latency_ms": result.latency_ms, "attempts": list(result.attempts),
                    "analysis": result.analysis.model_dump() if result.analysis else None,
                    "local_prediction": work.local_prediction, "affects_prediction": False,
                    "timing": "after_local_submission"}
                await asyncio.to_thread(self.store.finish_shadow, work.id, trace,
                                        "validated" if result.analysis else "unavailable")
            except Exception as exc:
                LOG.error("shadow_failure event=%s exception_type=%s", work.event_id, type(exc).__name__)
                await asyncio.to_thread(self.store.finish_shadow, work.id,
                    {"affects_prediction": False, "timing": "after_local_submission",
                     "error_type": type(exc).__name__}, "failed")

    async def process_claimed(self, work: Work) -> None:
        try:
            context = (self.telemetry.stage("eventdesk.job", **{"eventdesk.job_id": work.id,
                "eventdesk.slot": work.slot, "eventdesk.fixture": self.settings.fixture_mode,
                "eventdesk.model_sha256": self.model.sha256}) if self.telemetry else nullcontext())
            with context:
                await self.process(work)
        except Exception as exc:
            # Never print exception text: SDK exceptions can include signed URLs or credentials.
            LOG.error("worker_failure event=%s exception_type=%s", work.event.event_id, type(exc).__name__)
            await asyncio.to_thread(self.store.retry, work.id, "worker_" + type(exc).__name__, 2, time.time())

    async def heartbeat(self) -> None:
        details: dict[str, Any] = {"model_hash": self.model.sha256,
            "configuration_hash": self.configuration_hash,
            "synthetic_model": bool(self.model.artifact.get("fixture_only")),
            "llm_enabled": self.router is not None, "hybrid_enabled": self.blend is not None,
            "fixture_mode": self.settings.fixture_mode}
        while True:
            await asyncio.to_thread(self.store.pulse, "worker", details, time.time())
            # GUESS: ten-second operational heartbeat; alert after three misses, verified in health tests. # UNCALIBRATED GUESS
            await asyncio.sleep(10)

    async def dispatch(self) -> None:
        # GUESS: same eight simultaneous I/O jobs as the tested original pool; one idle poller # UNCALIBRATED GUESS
        # prevents multiplying empty database queries by eight on the small existing VPS.
        concurrency = 8
        active: set[asyncio.Task[None]] = set()
        while True:
            for task in tuple(active):
                if task.done():
                    active.remove(task)
                    task.result()
            if len(active) >= concurrency:
                await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                continue
            work = await asyncio.to_thread(self.store.claim, time.time())
            if work is None:
                # GUESS: bounded polling interval; latency must be measured under the busy-day test. # UNCALIBRATED GUESS
                await asyncio.sleep(0.25)
                continue
            active.add(asyncio.create_task(self.process_claimed(work)))


async def run() -> None:
    settings = Settings.from_env()
    store = Store(settings.database_url)
    configuration = None if settings.fixture_mode else CompetitionFreeze.model_validate_json(
        Path("competition-config.json").read_bytes())
    model = LocalModel(settings.model_path, expected_sha256=configuration.model_sha256 if configuration else None)
    if model.artifact.get("fixture_only") and not settings.fixture_mode:
        raise RuntimeError("Refusing synthetic fixture model in production")
    # SOURCE: configured official/provider destinations; ambient proxy variables must not reroute credentials.
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as http:
        telemetry = Telemetry()
        worker = Worker(settings, store, model, http, telemetry=telemetry)
        if not settings.fixture_mode:
            worker.configuration_hash = verify_freeze(Path("competition-config.json"), model,
                hybrid_enabled=worker.blend is not None,
                post_submission_evidence_enabled=worker.router is not None and worker.blend is None,
                provider_models={provider.name: provider.model for provider in providers_from_env()})
        await asyncio.to_thread(store.recover)
        LOG.info("worker_started model_hash=%s configuration_hash=%s fixture=%s",
                 model.sha256, worker.configuration_hash, settings.fixture_mode)
        try:
            await asyncio.gather(worker.heartbeat(), worker.shadow_loop(), worker.dispatch())
        finally:
            telemetry.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # Signed material query strings and auth-bearing SDK exceptions must not enter transport logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    asyncio.run(run())
