"""A bounded authenticated receipt path; no inference or external I/O before ACK."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from eventdesk.config import Settings
from eventdesk.llm import PROMPT_HASH, prompt_materials
from eventdesk.materials import input_hash
from eventdesk.schemas import Event, LLMAnalysis
from eventdesk.store import ConflictError, Store
from eventdesk.vendor.webhook_verification import WebhookVerificationError, verify_webhook

# SOURCE: official ACK maximum is 20 seconds; the stricter whole-receipt guard below
# is an UNCALIBRATED GUESS leaving network headroom, not an observed network guarantee.
RECEIPT_GUARD_SECONDS = 10

LOG = logging.getLogger("eventdesk.receipt")
RejectionReason = Literal[
    "unknown_submission_slot", "body_too_large", "body_timeout",
    "signature_headers_missing", "signature_timestamp_invalid",
    "signature_timestamp_outside_tolerance", "signature_verification_failed",
    "body_identity_mismatch", "missing_cutoff", "invalid_schema",
    "receipt_budget_exhausted", "conflicting_delivery", "database_acceptance_uncertain",
]


def _rejection(status: int, reason: RejectionReason, detail: str | None = None) -> HTTPException:
    # SOURCE: existing receipt response branches; never log body, headers, identity or exception text.
    LOG.warning("webhook_rejection status=%s reason=%s", status, reason)
    return HTTPException(status, detail)


def _signature_reason(error: WebhookVerificationError) -> RejectionReason:
    # SOURCE: fixed messages from the vendored official verifier; unknown text stays private.
    message = str(error)
    if message.startswith("missing one of Webhook-Id, Webhook-Timestamp, Webhook-Signature"):
        return "signature_headers_missing"
    if message == "Webhook-Timestamp is not an integer":
        return "signature_timestamp_invalid"
    if message.startswith("Webhook-Timestamp outside "):
        return "signature_timestamp_outside_tolerance"
    return "signature_verification_failed"


def create_app(settings: Settings, store: Store) -> FastAPI:
    app = FastAPI(title="Event Desk", docs_url=None, redoc_url=None)

    @app.get("/healthz")
    async def health() -> dict[str, object]:
        info = await asyncio.to_thread(store.health)
        info["fixture_mode"] = settings.fixture_mode
        return info

    @app.post("/competition/webhook")
    @app.post("/competition/webhook/{slot}")
    async def receive(request: Request, slot: str = "s1") -> Response:
        started = time.time()
        budget_started = time.monotonic()
        submission = settings.submissions.get(slot)
        if submission is None:
            raise _rejection(404, "unknown_submission_slot")
        # GUESS: 1 MiB ceiling for small official event metadata; not a content/model calibration. # UNCALIBRATED GUESS
        max_bytes = 1024 * 1024
        async def read_raw() -> bytes:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > max_bytes:
                    raise _rejection(413, "body_too_large")
            return bytes(raw)
        try:
            raw = await asyncio.wait_for(read_raw(), timeout=RECEIPT_GUARD_SECONDS)
        except TimeoutError:
            raise _rejection(503, "body_timeout", "Receipt body timeout") from None
        try:
            parsed = verify_webhook(raw_body=bytes(raw), headers=request.headers,
                                    secret=submission.webhook_secret)
            # SOURCE: RFC 8259 JSON forbids NaN/Infinity; reject before PostgreSQL serialization.
            json.dumps(parsed, allow_nan=False)
            event = Event.model_validate(parsed)
            delivery_id = request.headers["webhook-id"]
            if event.id != delivery_id:
                raise _rejection(400, "body_identity_mismatch", "Signed body/header identity mismatch")
            if event.event_type != "TEST" and event.knowledge_cutoff is None:
                raise _rejection(400, "missing_cutoff", "Missing knowledge cutoff")
        except WebhookVerificationError as exc:
            raise _rejection(401, _signature_reason(exc), "Signature verification failed") from None
        except UnicodeDecodeError:
            raise _rejection(401, "signature_verification_failed", "Signature verification failed") from None
        except (ValidationError, ValueError):
            raise _rejection(400, "invalid_schema", "Invalid event schema") from None
        try:
            remaining = RECEIPT_GUARD_SECONDS - (time.monotonic() - budget_started)
            if remaining <= 0:
                raise _rejection(503, "receipt_budget_exhausted", "Durable receipt unavailable")
            # Body reading, signature/schema validation and DB acceptance share one receipt budget.
            await asyncio.wait_for(asyncio.to_thread(store.receive, slot, delivery_id, bytes(raw), event, started),
                                   timeout=remaining)
        except ConflictError:
            raise _rejection(409, "conflicting_delivery", "Conflicting delivery") from None
        except (SQLAlchemyError, TimeoutError):
            # No 200 when durable acceptance is uncertain. A retry deduplicates a commit that finished late.
            raise _rejection(503, "database_acceptance_uncertain", "Durable receipt unavailable") from None
        return Response(status_code=200)

    @app.get("/api/predictions")
    async def predictions() -> list[dict[str, object]]:
        return await asyncio.to_thread(store.public_predictions)

    @app.get("/api/scoreboard")
    async def scoreboard() -> dict[str, object]:
        result = await asyncio.to_thread(store.scoreboard)
        # Public reports contain aggregates and hashes only, never private archives or provider credentials.
        report_path = Path("reports/archive-eval.json")
        if report_path.is_file():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            candidate = report["candidates"]["facts_baseline"]
            result["archive_validation"] = {"quarter": report["config"]["validation_quarter"],
                "model_sha256": report["artifact_sha256"],
                "delta_r_squared_imputed": candidate["score"]["delta_r_squared_imputed"],
                "scorer_rows": candidate["score"]["n_obs"], "predicted_rows": candidate["validation_rows"],
                "limits": report["config"]["limits"]}
        else:
            result["archive_validation"] = None
        return result

    @app.get("/api/events/{event_id}")
    async def event_detail(event_id: str, slot: str = "s1") -> dict[str, object]:
        if slot not in settings.submissions:
            raise HTTPException(404)
        result = await asyncio.to_thread(store.public_event, event_id, slot)
        if result is None:
            raise HTTPException(404)
        return result

    @app.get("/api/competition")
    async def official_observations() -> dict[str, object]:
        result = await asyncio.to_thread(store.competition_overview)
        result["configured_slots"] = list(settings.submissions)
        return result

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")

    @app.get("/walkthrough", response_class=HTMLResponse)
    async def walkthrough_page() -> str:
        return Path(__file__).with_name("walkthrough.html").read_text(encoding="utf-8")

    @app.get("/api/walkthrough")
    async def walkthrough_record() -> dict[str, object]:
        # SOURCE: one generated synthetic report. Never query/seed the production event ledger here.
        path = Path("reports/walkthrough.json")
        if not path.is_file():
            raise HTTPException(503, "Walkthrough has not been generated")
        result = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(result, dict) or result.get("schema_version") != "eventdesk-walkthrough-v1"
                or result.get("fixture_only") is not True or result.get("external_requests") != 0
                or not isinstance(result.get("record"), dict) or result["record"].get("state") != "simulated"):
            raise HTTPException(503, "Walkthrough provenance unavailable")
        result["ai_review"] = None
        result["ai_review_status"] = "not_run"
        proof_path = Path("reports/shadow-provider-smoke.json")
        if proof_path.is_file():
            try:
                proof = json.loads(proof_path.read_text(encoding="utf-8"))
                trace = proof["analysis_trace"]
                items = prompt_materials(result["record"]["official_items"])
                if (proof["schema_version"] != "eventdesk-shadow-smoke-v1" or proof["fixture_only"] is not True
                        or proof["external_official_requests"] != 0 or proof["prediction_unchanged"] is not True
                        or proof["inputs_sha256"] != result["record"]["inputs_hash"]
                        or proof["model_sha256"] != result["record"]["model_hash"]
                        or trace["llm_inputs_hash"] != input_hash(items) or trace["prompt_hash"] != PROMPT_HASH
                        or trace["local_prediction"] != result["record"]["prediction"]["predictions"][0]["predicted_percentile"]
                        or proof["shadow_state"] not in {"validated", "unavailable", "failed"}
                        or trace["affects_prediction"] is not False or trace["timing"] != "after_local_submission"):
                    raise ValueError("Different evidence provenance")
                if proof["shadow_state"] == "validated":
                    LLMAnalysis.model_validate(trace["analysis"]).validate_quotes(items)
                elif trace.get("analysis") is not None:
                    raise ValueError("Unvalidated evidence")
                result["ai_review"] = proof
                result["ai_review_status"] = "retained_separate_provider_smoke"
            except (KeyError, TypeError, ValueError):
                # A broken optional report cannot replace the actual local demo or manufacture evidence.
                result["ai_review_status"] = "invalid_or_mismatched_provenance"
        return result

    return app


def app_factory() -> FastAPI:
    settings = Settings.from_env()
    store = Store(settings.database_url)
    if settings.fixture_mode:
        store.initialize_fixture()
    return create_app(settings, store)
