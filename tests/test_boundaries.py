import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eventdesk.materials import facts_text, feature_row, select_items
from eventdesk.schemas import LLMAnalysis, Prediction
from eventdesk.vendor.webhook_verification import WebhookVerificationError, verify_webhook


def test_official_vectors_and_rotation():
    vectors = json.loads(Path("tests-vectors.json").read_text())["vectors"]
    for vector in vectors:
        for secret in vector.get("secrets", [vector.get("secret")]):
            headers = {"Webhook-Id": vector["webhook_id"], "Webhook-Timestamp": str(vector["timestamp"]),
                       "Webhook-Signature": vector["expected_signature_header"]}
            assert verify_webhook(raw_body=vector["raw_body"].encode(), headers=headers,
                                  secret=secret, now=vector["timestamp"])["id"] == vector["webhook_id"]
            with pytest.raises(WebhookVerificationError):
                verify_webhook(raw_body=(vector["raw_body"] + " ").encode(), headers=headers,
                               secret=secret, now=vector["timestamp"])
            with pytest.raises(WebhookVerificationError):
                verify_webhook(raw_body=vector["raw_body"].encode(), headers=headers,
                               secret=secret, now=vector["timestamp"] + 301)


def test_features_ignore_returns_and_unknown_items():
    record = {"disclosure": {"items": [{"id": "earnings-call-facts", "content": ["Revenue rose."]},
                                          {"id": "future-new-kind", "content": {"unknown": True}}]},
              "event_returns": {"SECRET_OUTCOME": {"car1": 900}}, "metrics": {"future": 999}}
    assert facts_text(select_items(record)) == "Revenue rose."
    row = feature_row(select_items(record), enriched=True)
    assert row["preview_missing"] == 1
    assert "SECRET_OUTCOME" not in json.dumps(row)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.01, 1.01])
def test_prediction_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        Prediction(identifier_value="TEST", predicted_percentile=value)


def test_quotes_must_exist_in_supplied_materials():
    analysis = LLMAnalysis(beat_vs_buyside_bar=1, guidance_change=1, tone=0, new_risks=-1,
                           surprise_vs_preview=0, confidence=0.5,
                           evidence=[{"item_id": "earnings-call-facts", "quote": "Revenue rose"}])
    analysis.validate_quotes({"earnings-call-facts": ["Revenue rose this quarter."]})
    with pytest.raises(ValueError):
        analysis.validate_quotes({"earnings-call-facts": ["Nothing resembling that quote"]})
