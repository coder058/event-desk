"""A bounded authenticated receipt path; no inference or external I/O before ACK."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from eventdesk.config import Settings
from eventdesk.schemas import Event
from eventdesk.store import ConflictError, Store
from eventdesk.vendor.webhook_verification import WebhookVerificationError, verify_webhook


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
        submission = settings.submissions.get(slot)
        if submission is None:
            raise HTTPException(404)
        # GUESS: 1 MiB ceiling for small official event metadata; not a content/model calibration.
        max_bytes = 1024 * 1024
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > max_bytes:
                raise HTTPException(413)
        try:
            parsed = verify_webhook(raw_body=bytes(raw), headers=request.headers,
                                    secret=submission.webhook_secret)
            event = Event.model_validate(parsed)
            delivery_id = request.headers["webhook-id"]
            if event.id != delivery_id:
                raise HTTPException(400, "Signed body/header identity mismatch")
            if event.event_type != "TEST" and event.knowledge_cutoff is None:
                raise HTTPException(400, "Missing knowledge cutoff")
        except (WebhookVerificationError, UnicodeDecodeError):
            raise HTTPException(401, "Signature verification failed") from None
        except ValidationError:
            raise HTTPException(400, "Invalid event schema") from None
        try:
            # SOURCE: 20-second official ACK limit; this stricter 10-second guard is an UNCALIBRATED GUESS
            # leaving room for network/verification. PostgreSQL statement timeout is configured separately.
            await asyncio.wait_for(asyncio.to_thread(store.receive, slot, delivery_id, bytes(raw), event, started),
                                   timeout=10)
        except ConflictError:
            raise HTTPException(409, "Conflicting delivery") from None
        except (SQLAlchemyError, TimeoutError):
            # No 200 when durable acceptance is uncertain. A retry deduplicates a commit that finished late.
            raise HTTPException(503, "Durable receipt unavailable") from None
        return Response(status_code=200)

    @app.get("/api/predictions")
    async def predictions() -> list[dict[str, object]]:
        return await asyncio.to_thread(store.public_predictions)

    @app.get("/api/events/{event_id}")
    async def event_detail(event_id: str) -> dict[str, object]:
        result = await asyncio.to_thread(store.public_event, event_id)
        if result is None:
            raise HTTPException(404)
        return result

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")

    return app


def app_factory() -> FastAPI:
    settings = Settings.from_env()
    store = Store(settings.database_url)
    if settings.fixture_mode:
        store.initialize_fixture()
    return create_app(settings, store)
