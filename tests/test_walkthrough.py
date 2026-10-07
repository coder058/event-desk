import asyncio
import importlib.util
from pathlib import Path

import pytest


def generator():
    spec = importlib.util.spec_from_file_location("walkthrough_fixture", Path("fixtures/build_walkthrough.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.generate


def test_walkthrough_reuses_receipt_and_worker_without_external_io_or_live_history(model, tmp_path):
    proof = asyncio.run(generator()(model, tmp_path/"new.sqlite"))
    assert proof["fixture_only"] is True and proof["external_requests"] == 0
    assert proof["model_origin"] == "synthetic_fixture"
    receipt = proof["receipt_checks"]
    assert (receipt["signed_ack_status"], receipt["duplicate_status"], receipt["modified_signature_status"],
            receipt["conflicting_delivery_status"]) == (200, 200, 401, 409)
    record = proof["record"]
    assert record["state"] == "simulated" and record["analysis_trace"] is None
    trace = record["local_trace"]
    assert trace["prediction"] == pytest.approx(record["prediction"]["predictions"][0]["predicted_percentile"])
    assert trace["linear_total"] == pytest.approx(trace["intercept"]+trace["other_terms_contribution"]
        +sum(term["contribution"] for term in trace["terms"]))


def test_walkthrough_cannot_overwrite_an_existing_database(model, tmp_path):
    existing = tmp_path/"production-looking.sqlite"
    existing.write_bytes(b"untouched")
    with pytest.raises(ValueError, match="new disposable"):
        asyncio.run(generator()(model, existing))
    assert existing.read_bytes() == b"untouched"


def test_public_demo_is_separate_from_live_ledger_and_rejects_mislabeled_results(settings, store, model, tmp_path, monkeypatch):
    import json

    from fastapi.testclient import TestClient

    from eventdesk.api import create_app
    proof = asyncio.run(generator()(model, tmp_path/"demo.sqlite"))
    monkeypatch.chdir(tmp_path)
    report = tmp_path/"reports/walkthrough.json"
    report.parent.mkdir()
    report.write_text(json.dumps(proof), encoding="utf-8")
    client = TestClient(create_app(settings, store))
    assert client.get("/api/walkthrough").json()["record"]["state"] == "simulated"
    assert client.get("/walkthrough").status_code == 200
    assert client.get("/api/predictions").json() == []
    assert store.health()["states"] == {}
    proof["record"]["state"] = "api_accepted"
    report.write_text(json.dumps(proof), encoding="utf-8")
    assert client.get("/api/walkthrough").status_code == 503
    report.unlink()
    assert client.get("/api/walkthrough").status_code == 503
