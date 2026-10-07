"""Generate an isolated signed-event walkthrough; never touch production or send a prediction."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from eventdesk.api import create_app
from eventdesk.config import Settings, Submission
from eventdesk.model import LocalModel
from eventdesk.schemas import Event
from eventdesk.store import Store
from eventdesk.worker import Worker

# SOURCE: public official verification vector, not an owner credential.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"
# PLACEHOLDER: fictional company statements solely to demonstrate the actual pipeline.
MATERIALS = {"items": [
    {"id": "earnings-call-facts", "content": [
        "Revenue increased as demand for enterprise software improved.",
        "Management raised full-year revenue guidance.",
        "Operating margin declined due to higher investment in product development.",
        "Management noted uncertainty in customer spending and longer sales cycles."]},
    {"id": "earnings-preview", "content":
        "The fictional preview expected revenue growth and unchanged guidance. "
        "Investors were watching margin pressure and customer demand."}]}


def signed(raw: bytes, delivery_id: str) -> dict[str, str]:
    timestamp = str(int(time.time()))
    key = base64.urlsafe_b64decode(SECRET.removeprefix("whsec_"))
    signature = base64.b64encode(hmac.new(key,
        delivery_id.encode()+b"."+timestamp.encode()+b"."+raw, hashlib.sha256).digest()).decode()
    return {"Webhook-Id": delivery_id, "Webhook-Timestamp": timestamp,
            "Webhook-Signature": "v1,"+signature, "Content-Type": "application/json"}


async def generate(model: LocalModel, database: Path) -> dict:
    if database.exists():
        raise ValueError("Walkthrough requires a new disposable database")
    store = Store("sqlite:///"+str(database))
    store.initialize_fixture()
    settings = Settings(str(store.engine.url), Path("unused-fixture-path"),
        {"s1": Submission("s1", "fixture-only", SECRET)}, True, frozenset())
    # SOURCE: metadata time is generation time; all event/company content is explicitly fictional.
    event = Event(id="walkthrough-fictional-event", event_id="walkthrough-fictional-event",
        event_type="EARNINGS_RELEASE", knowledge_cutoff=datetime.now(UTC),
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "DEMO"}],
        fixture_materials=MATERIALS)
    raw = event.model_dump_json().encode()
    outgoing = []
    def no_network(request):
        outgoing.append(str(request.url))
        raise AssertionError("Walkthrough attempted external I/O")
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(settings, store)),
                                     base_url="http://fixture.invalid") as api:
            headers = signed(raw, event.id)
            started = time.perf_counter()
            receipt = await api.post("/competition/webhook", content=raw, headers=headers)
            ack_ms = (time.perf_counter()-started)*1000  # SOURCE: measured local ASGI request interval.
            assert receipt.status_code == 200
            assert store.health()["states"] == {"pending": 1}
            duplicate = await api.post("/competition/webhook", content=raw, headers=headers)
            changed = await api.post("/competition/webhook", content=raw+b" ", headers=headers)
            conflict = await api.post("/competition/webhook", content=raw+b" ", headers=signed(raw+b" ", event.id))
            assert duplicate.status_code == 200 and changed.status_code == 401 and conflict.status_code == 409
        work = store.claim(time.time())
        assert work is not None
        async with httpx.AsyncClient(transport=httpx.MockTransport(no_network)) as http:
            await Worker(settings, store, model, http).process(work)
        assert outgoing == []
        record = store.public_event(event.event_id)
        assert record and record["state"] == "simulated" and record["analysis_trace"] is None
        assert record["local_trace"]["kind"] == "tf_idf_ridge_computation", "Fixture did not produce a text computation"
        return {"schema_version": "eventdesk-walkthrough-v1", "fixture_only": True,
            "generated_at": datetime.now(UTC).isoformat(), "input_origin": "fictional_company_and_materials",
            "model_origin": "synthetic_fixture" if model.artifact.get("fixture_only") else "trained_archive_model",
            "database_origin": "disposable_local_sqlite", "external_requests": len(outgoing),
            "signed_body_sha256": hashlib.sha256(raw).hexdigest(),
            "receipt_checks": {"signed_ack_status": receipt.status_code, "duplicate_status": duplicate.status_code,
                "modified_signature_status": changed.status_code, "conflicting_delivery_status": conflict.status_code,
                "local_asgi_ack_ms": ack_ms}, "record": record,
            "limits": "Synthetic inputs; actual receipt/worker/math in disposable SQLite. No broker, official POST, score or live latency."}
    finally:
        store.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("artifacts/local-model.joblib"))
    parser.add_argument("--output", type=Path, default=Path("reports/walkthrough.json"))
    args = parser.parse_args()
    model = LocalModel(args.model)
    with tempfile.TemporaryDirectory(prefix="eventdesk-walkthrough-") as temporary:
        proof = asyncio.run(generate(model, Path(temporary)/"demo.sqlite"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(proof, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "fixture_only": True,
                      "external_requests": proof["external_requests"], "state": proof["record"]["state"]}))


if __name__ == "__main__":
    main()
