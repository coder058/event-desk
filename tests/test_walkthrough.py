import asyncio
import importlib.util
import json
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


@pytest.mark.parametrize("damage", [None, "inputs", "model", "prompt", "prediction", "quote", "affects", "state", "json"])
def test_optional_ai_proof_requires_same_inputs_model_forecast_and_actual_quotes(
        settings, store, model, tmp_path, monkeypatch, damage):
    from fastapi.testclient import TestClient

    from eventdesk.api import create_app
    from eventdesk.llm import PROMPT_HASH, prompt_materials
    from eventdesk.materials import input_hash

    base = asyncio.run(generator()(model, tmp_path/"demo.sqlite"))
    items = prompt_materials(base["record"]["official_items"])
    # PLACEHOLDER: this constructed report tests attribution guards; it is not a real provider call.
    proof = {
        "schema_version": "eventdesk-shadow-smoke-v1", "fixture_only": True,
        "external_official_requests": 0, "prediction_unchanged": True,
        "inputs_sha256": base["record"]["inputs_hash"], "model_sha256": base["record"]["model_hash"],
        "shadow_state": "validated", "analysis_trace": {
            "llm_inputs_hash": input_hash(items), "prompt_hash": PROMPT_HASH,
            "local_prediction": base["record"]["prediction"]["predictions"][0]["predicted_percentile"],
            "affects_prediction": False, "timing": "after_local_submission",
            "analysis": {"beat_vs_buyside_bar": 0, "guidance_change": 0, "tone": 0, "new_risks": 0,
                "surprise_vs_preview": 0, "confidence": 0,
                "evidence": [{"item_id": "earnings-call-facts", "quote": items["earnings-call-facts"][0]}]},
        },
    }
    trace = proof["analysis_trace"]
    if damage in {"inputs", "model"}:
        proof[damage+"_sha256"] = "different"
    elif damage == "prompt":
        trace["prompt_hash"] = "different"
    elif damage == "prediction":
        trace["local_prediction"] = "different"
    elif damage == "quote":
        trace["analysis"]["evidence"][0]["quote"] = "Fabricated quotation absent from the supplied source."
    elif damage == "affects":
        trace["affects_prediction"] = True
    elif damage == "state":
        proof["shadow_state"] = "invented"
    monkeypatch.chdir(tmp_path)
    reports = tmp_path/"reports"
    reports.mkdir()
    (reports/"walkthrough.json").write_text(json.dumps(base), encoding="utf-8")
    (reports/"shadow-provider-smoke.json").write_text("{" if damage == "json" else json.dumps(proof), encoding="utf-8")
    client = TestClient(create_app(settings, store))
    response = client.get("/api/walkthrough")
    assert response.status_code == 200
    result = response.json()
    assert result["record"] == base["record"]
    assert result["ai_review"] == (proof if damage is None else None)
    assert result["ai_review_status"] == (
        "retained_separate_provider_smoke" if damage is None else "invalid_or_mismatched_provenance")
    assert client.get("/api/predictions").json() == []
    assert store.health()["states"] == {}
