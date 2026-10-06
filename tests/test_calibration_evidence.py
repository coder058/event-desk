import copy
import importlib

import pytest

from eventdesk.llm import PROMPT_HASH
from eventdesk.materials import input_hash, select_items


def fixture_data():
    # PLACEHOLDER: synthetic archive/LLM output validates provenance boundaries, not predictive performance.
    records = [{"event_id": "fixture", "items": [{"id": "earnings-call-facts", "content": ["Revenue increased."]}]}]
    attempt = {"event_id": "fixture", "quarter": "2026Q2", "provider": "groq", "model": "fixture-model",
        "prompt_hash": PROMPT_HASH, "inputs_hash": input_hash(select_items(records[0])),
        "analysis": {"beat_vs_buyside_bar": 1, "guidance_change": 0, "tone": 0, "new_risks": 0,
            "surprise_vs_preview": 0, "confidence": .5,
            "evidence": [{"item_id": "earnings-call-facts", "quote": "Revenue increased."}]}}
    return records, attempt


def test_calibration_uses_exact_archive_inputs_and_current_prompt(monkeypatch):
    monkeypatch.syspath_prepend("research")
    module = importlib.import_module("probe_blend")
    records, attempt = fixture_data()
    args = {"quarter": "2026Q2", "provider": "groq", "model": "fixture-model"}
    assert list(module.validated_samples(records, [attempt, copy.deepcopy(attempt)], **args)) == ["fixture"]
    old = {**attempt, "prompt_hash": "old-prompt"}
    assert module.validated_samples(records, [old], **args) == {}
    altered = {**attempt, "inputs_hash": "not-the-source"}
    with pytest.raises(ValueError, match="different archive inputs"):
        module.validated_samples(records, [altered], **args)
    with pytest.raises(ValueError, match="quarter/event"):
        module.validated_samples(records, [{**attempt, "quarter": "2026Q3"}], **args)


def test_calibration_rejects_quote_forgery_and_favorable_retry_selection(monkeypatch):
    monkeypatch.syspath_prepend("research")
    module = importlib.import_module("probe_blend")
    records, attempt = fixture_data()
    args = {"quarter": "2026Q2", "provider": "groq", "model": "fixture-model"}
    altered = copy.deepcopy(attempt)
    altered["analysis"]["evidence"][0]["quote"] = "Invented material."
    with pytest.raises(ValueError, match="absent"):
        module.validated_samples(records, [altered], **args)
    altered = copy.deepcopy(attempt)
    altered["analysis"]["tone"] = 1
    with pytest.raises(ValueError, match="favorable retry"):
        module.validated_samples(records, [attempt, altered], **args)
