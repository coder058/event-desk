import asyncio
import copy
import gzip
import importlib
import json
import time
from pathlib import Path

import pytest

from eventdesk.llm import PROMPT_HASH, AnalysisResult, Provider
from eventdesk.materials import input_hash, select_items
from eventdesk.quotas import Limits, Quotas
from eventdesk.schemas import LLMAnalysis


@pytest.fixture
def cached_collection(monkeypatch, tmp_path, store):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "research"))
    module = importlib.import_module("collect_llm")
    # PLACEHOLDER: fixture event, timestamps, model and analysis test provenance;
    # no free-provider calls, calibration or new scores are produced.
    record = {"event_id": "fixture", "event_datetime": "2026-04-01T12:00:00Z",
              "items": [{"id": "earnings-call-facts", "content": ["Revenue increased."]}]}
    analysis = {"beat_vs_buyside_bar": 1, "guidance_change": 0, "tone": 0, "new_risks": 0,
                "surprise_vs_preview": 0, "confidence": .5,
                "evidence": [{"item_id": "earnings-call-facts", "quote": "Revenue increased."}]}
    attempt = {"event_id": "fixture", "quarter": "2026Q2", "provider": "groq", "model": "fixture-model",
               "prompt_hash": PROMPT_HASH, "inputs_hash": input_hash(select_items(record)), "analysis": analysis}
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output = output_dir / "llm-groq-2026Q2.jsonl"
    archive = tmp_path / "2026Q2.jsonl.gz"
    calls = []
    # PLACEHOLDER: enough synthetic admission capacity for one mock collection.
    provider = Provider("groq", "fixture-model", "fixture-not-owner", Limits(1, 1, 100000, 100000))
    monkeypatch.setenv("DATABASE_URL", "postgresql://fixture-not-used")
    monkeypatch.setattr(module, "Store", lambda _: store)
    monkeypatch.setattr(module, "providers_from_env", lambda: (provider,))
    monkeypatch.setattr("sys.argv", ["collect_llm", "--quarter", "2026Q2", "--provider", "groq", "--count", "1",
                                     "--archive-dir", str(tmp_path), "--output-dir", str(output_dir)])

    class MockRouter:
        def __init__(self, quotas, http, providers):
            self.quotas = quotas

        async def analyze(self, items, deadline):
            calls.append(items)
            return AnalysisResult(LLMAnalysis.model_validate(analysis), "groq", "fixture-model", 0, ())

    monkeypatch.setattr(module, "Router", MockRouter)

    def run(attempts, records=None):
        with gzip.open(archive, "wt", encoding="utf-8") as stream:
            stream.write("".join(json.dumps(r) + "\n" for r in (records if records is not None else [record])))
        output.write_text("".join(json.dumps(r) + "\n" for r in attempts), encoding="utf-8")
        asyncio.run(module.main())
        return [json.loads(line) for line in output.read_text().splitlines()]

    return run, attempt, record, calls, store


def test_valid_identical_cache_is_skipped_without_calls_or_quota_use(cached_collection):
    run, attempt, _, calls, store = cached_collection
    rows = run([attempt, copy.deepcopy(attempt)])
    assert rows == [attempt, attempt] and calls == []
    assert Quotas(store).summary() == {}


@pytest.mark.parametrize("fault", ["inputs", "quote", "quarter", "event", "schema", "missing_hash", "conflict"])
def test_corrupt_matching_cache_fails_closed_before_mock_provider(cached_collection, fault):
    run, attempt, _, calls, _ = cached_collection
    changed = copy.deepcopy(attempt)
    if fault == "inputs":
        changed["inputs_hash"] = "not-the-archive"
    elif fault == "quote":
        changed["analysis"]["evidence"][0]["quote"] = "Invented quotation."
    elif fault == "quarter":
        changed["quarter"] = "2026Q3"
    elif fault == "event":
        changed["event_id"] = "outside-archive"
    elif fault == "schema":
        changed["analysis"]["tone"] = "not-a-score"
    elif fault == "missing_hash":
        del changed["inputs_hash"]
    else:
        changed["analysis"]["tone"] = 1
    attempts = [attempt, changed] if fault == "conflict" else [changed]
    with pytest.raises((ValueError, KeyError)):
        run(attempts)
    assert calls == []


@pytest.mark.parametrize("ignored", ["prompt", "model", "provider", "failed"])
def test_unrelated_or_failed_cache_does_not_suppress_collection(cached_collection, ignored):
    run, attempt, record, calls, _ = cached_collection
    changed = copy.deepcopy(attempt)
    if ignored == "prompt":
        changed["prompt_hash"] = "older-prompt"
    elif ignored == "model":
        changed["model"] = "other-model"
    elif ignored == "provider":
        changed["provider"] = "gemini"
    else:
        changed["analysis"] = None
    rows = run([changed])
    assert calls == [select_items(record)] and len(rows) == 2
    assert rows[-1]["inputs_hash"] == attempt["inputs_hash"]
    assert rows[-1]["analysis"] == attempt["analysis"]


def test_duplicate_archive_identity_fails_before_skipping_cache(cached_collection):
    run, attempt, record, calls, _ = cached_collection
    with pytest.raises(ValueError, match="duplicated"):
        run([attempt], [record, copy.deepcopy(record)])
    assert calls == []


def test_invalid_cache_cannot_be_hidden_by_provider_cooldown(cached_collection):
    # PLACEHOLDER: synthetic cooldown checks validation order, not an API quota.
    run, attempt, _, calls, store = cached_collection
    quotas = Quotas(store)
    usage = quotas.reserve("groq", 1, Limits(1, 1, 100000, 100000), time.time())
    quotas.settle(usage, None, "http_429", cooldown_seconds=60, now=time.time())
    changed = {**attempt, "inputs_hash": "not-the-archive"}
    with pytest.raises(ValueError, match="different archive inputs"):
        run([changed])
    assert calls == []
