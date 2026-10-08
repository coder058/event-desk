import hashlib
import json
import logging
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from test_delivery import event, signed

from eventdesk.api import create_app


@pytest.mark.parametrize("case,status,reason", [
    ("missing_signature", 401, "signature_headers_missing"),
    ("expired_signature", 401, "signature_timestamp_outside_tolerance"),
    ("invalid_timestamp", 401, "signature_timestamp_invalid"),
    ("changed_body", 401, "signature_verification_failed"),
    ("invalid_schema", 400, "invalid_schema"),
    ("identity_mismatch", 400, "body_identity_mismatch"),
    ("invalid_cutoff", 400, "invalid_schema"),
    ("unknown_slot", 404, "unknown_submission_slot"),
])
def test_rejections_log_only_status_and_enumerated_reason(settings, store, caplog, case, status, reason):
    # SOURCE: statuses preserve the existing receiver branches; inputs are synthetic rejection fixtures.
    e = event()
    e = e.model_copy(update={"private_metadata": "never-log-body-sentinel"})
    raw = e.model_dump_json().encode()
    headers = signed(raw, e.id)
    url = "/competition/webhook"
    if case == "missing_signature":
        headers.pop("Webhook-Signature")
    elif case == "expired_signature":
        # SOURCE: deliberately outside the vendored official signature tolerance.
        from eventdesk.vendor.webhook_verification import DEFAULT_TOLERANCE_SECONDS
        headers["Webhook-Timestamp"] = str(int(time.time()) - DEFAULT_TOLERANCE_SECONDS - 1)
    elif case == "invalid_timestamp":
        headers["Webhook-Timestamp"] = "never-log-header-sentinel"
    elif case == "changed_body":
        raw += b" "
    elif case == "invalid_schema":
        raw = b'{"private_metadata":"never-log-body-sentinel"}'
        headers = signed(raw, e.id)
    elif case == "identity_mismatch":
        headers = signed(raw, "different-synthetic-delivery")
    elif case == "invalid_cutoff":
        # PLACEHOLDER: timezone-free metadata remains invalid when the field is supplied.
        malformed = e.model_dump(mode="json")
        malformed["knowledge_cutoff"] = "2026-01-01T00:00:00"
        raw = json.dumps(malformed).encode()
        headers = signed(raw, e.id)
    elif case == "unknown_slot":
        url += "/unconfigured"
    with caplog.at_level(logging.WARNING, logger="eventdesk.receipt"):
        response = TestClient(create_app(settings, store)).post(url, content=raw, headers=headers)
    assert response.status_code == status
    records = [r for r in caplog.records if r.name == "eventdesk.receipt"]
    assert [r.getMessage() for r in records] == [f"webhook_rejection status={status} reason={reason}"]
    assert "never-log-" not in caplog.text
    assert headers.get("Webhook-Signature", "missing-fixture-signature") not in caplog.text
    assert e.id not in caplog.text
    assert store.health()["states"] == {}


def test_conflicting_delivery_has_a_distinct_safe_reason(settings, store, caplog):
    e = event()
    raw = e.model_dump_json().encode()
    client = TestClient(create_app(settings, store))
    assert client.post("/competition/webhook", content=raw, headers=signed(raw, e.id)).status_code == 200
    changed = raw + b" "
    with caplog.at_level(logging.WARNING, logger="eventdesk.receipt"):
        response = client.post("/competition/webhook", content=changed, headers=signed(changed, e.id))
    assert response.status_code == 409
    assert [r.getMessage() for r in caplog.records if r.name == "eventdesk.receipt"] == [
        "webhook_rejection status=409 reason=conflicting_delivery"]
    assert store.health()["states"] == {"pending": 1}


def test_oversized_body_has_safe_reason(settings, store, caplog):
    # SOURCE: one byte beyond the receiver's existing 1 MiB ceiling.
    raw = b"x" * (1024 * 1024 + 1)
    with caplog.at_level(logging.WARNING, logger="eventdesk.receipt"):
        response = TestClient(create_app(settings, store)).post("/competition/webhook", content=raw)
    assert response.status_code == 413
    assert [r.getMessage() for r in caplog.records if r.name == "eventdesk.receipt"] == [
        "webhook_rejection status=413 reason=body_too_large"]
    assert store.health()["states"] == {}


@pytest.mark.parametrize("fault,reason", [
    ("db", "database_acceptance_uncertain"),
    ("budget", "receipt_budget_exhausted"),
])
def test_uncertain_receipt_logs_no_exception_text(settings, store, caplog, monkeypatch, fault, reason):
    import eventdesk.api as module
    e = event()
    raw = e.model_dump_json().encode()
    if fault == "db":
        def fail_receive(*args):
            raise SQLAlchemyError("never-log-database-sentinel")
        monkeypatch.setattr(store, "receive", fail_receive)
    else:
        # PLACEHOLDER: local clock fixture exhausts the existing guard without touching asyncio's clock.
        readings = iter((0, module.RECEIPT_GUARD_SECONDS))
        monkeypatch.setattr(module, "time", SimpleNamespace(time=time.time, monotonic=lambda: next(readings)))
    with caplog.at_level(logging.WARNING, logger="eventdesk.receipt"):
        response = TestClient(create_app(settings, store)).post(
            "/competition/webhook", content=raw, headers=signed(raw, e.id))
    assert response.status_code == 503
    assert response.json() == {"detail": "Durable receipt unavailable"}
    assert [r.getMessage() for r in caplog.records if r.name == "eventdesk.receipt"] == [
        f"webhook_rejection status=503 reason={reason}"]
    assert "never-log-" not in caplog.text
    assert store.health()["states"] == {}


def test_same_signed_request_at_two_fixture_origins_preserves_app_bytes(settings, store):
    # PLACEHOLDER: these ASGI-only origins do not run TLS, HAProxy or Caddy.
    # SOURCE: port 80 versus default HTTPS reflects the two origin forms being investigated.
    e = event()
    e = e.model_copy(update={"metadata": "naïve — 🚀\nexact whitespace"})
    # SOURCE: the existing TLS mux fixture uses indented Unicode to check signed byte preservation.
    raw = e.model_dump_json(indent=2).encode()
    headers = signed(raw, e.id)
    captured = []
    app = create_app(settings, store)

    async def capture(scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        chunks = []

        async def read():
            message = await receive()
            if message["type"] == "http.request":
                chunks.append(message.get("body", b""))
            return message

        await app(scope, read, send)
        captured.append({"body_sha256": hashlib.sha256(b"".join(chunks)).hexdigest(),
            "signing_headers": {key: value for key, value in scope["headers"]
                                if key.startswith(b"webhook-")}})

    for origin in ("http://fixture:80", "https://fixture"):
        with TestClient(capture, base_url=origin) as client:
            assert client.post("/competition/webhook", content=raw, headers=headers).status_code == 200
    expected = {"body_sha256": hashlib.sha256(raw).hexdigest(),
        "signing_headers": {key.lower().encode(): value.encode() for key, value in headers.items()
                            if key.lower().startswith("webhook-")}}
    assert captured == [expected, expected]
    assert store.health()["states"] == {"pending": 1}
