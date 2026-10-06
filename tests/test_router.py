import asyncio
import json
import time

import httpx

from eventdesk.llm import Provider, Router, safe_limit_error, safe_quota_headers
from eventdesk.quotas import Limits, Quotas


def valid_analysis(quote="Revenue increased"):
    return {"beat_vs_buyside_bar": 1, "guidance_change": 0, "tone": 0, "new_risks": 0,
            "surprise_vs_preview": 0, "confidence": .5,
            "evidence": [{"item_id": "earnings-call-facts", "quote": quote}]}


def test_quota_reservation_persists_and_cooldown_blocks_after_restart(store):
    # PLACEHOLDER: small synthetic limits make admission-control boundaries testable.
    limits = Limits(2, 5, 100, 200)
    quotas = Quotas(store)
    first = quotas.reserve("fixture", 60, limits, 1000)
    assert first is not None
    assert Quotas(store).reserve("fixture", 60, limits, 1000) is None
    quotas.settle(first, 10, "validated", now=1000)
    second = quotas.reserve("fixture", 60, limits, 1000)
    assert second is not None
    quotas.settle(second, None, "http_429", cooldown_seconds=60, now=1000)
    assert Quotas(store).reserve("fixture", 1, limits, 1061) is not None
    assert Quotas(store).reserve("fixture", 1, limits, 1059) is None


def test_router_503_fails_over_and_quotes_validated(store):
    quotas = Quotas(store)
    providers = (Provider("gemini", "fixture-gemini", "fixture-key", Limits(10, 100, 100000, 100000)),
                 Provider("groq", "fixture-groq", "fixture-key", Limits(10, 100, 100000, 100000)))
    urls = []
    def handler(request):
        urls.append(str(request.url))
        assert "fixture-key" not in str(request.url)
        if "googleapis" in str(request.url):
            return httpx.Response(503)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(valid_analysis())}}],
                                         "usage": {"total_tokens": 400}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            return await Router(quotas, http, providers).analyze(
                {"earnings-call-facts": ["Revenue increased this quarter."]}, time.time() + 300)
    result = asyncio.run(run())
    assert result.provider == "groq" and result.analysis is not None
    assert result.attempts[0]["status"] == "http_503"
    assert len(urls) == 2


def test_router_budget_never_spends_submission_reserve(store):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            provider = Provider("gemini", "fixture-model", "fixture-key", Limits(1, 1, 100000, 100000))
            return await Router(Quotas(store), http, (provider,)).analyze(
                {"earnings-call-facts": ["Revenue increased."]}, time.time() + 29)
    result = asyncio.run(run())
    assert not calls and result.analysis is None
    assert result.attempts[0]["status"] == "deadline_reserve"


def test_router_rejects_fabricated_quote(store):
    def handler(request):
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": json.dumps(valid_analysis("Fabricated quote"))}]}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            provider = Provider("gemini", "fixture-model", "fixture-key", Limits(1, 1, 100000, 100000))
            return await Router(Quotas(store), http, (provider,)).analyze(
                {"earnings-call-facts": ["Revenue increased."]}, time.time() + 300)
    result = asyncio.run(run())
    assert result.analysis is None
    assert result.attempts[0]["status"] == "evidence_not_verbatim"
    assert result.attempts[-1]["status"].startswith("invalid_or_unavailable")


def test_quota_diagnostics_exclude_secrets_and_nonfinite_values():
    headers = httpx.Headers({"Authorization": "never-emit", "X-Provider-Diagnostic": "never-emit",
        "x-ratelimit-limit-tokens": "8000", "x-ratelimit-remaining-tokens": "NaN",
        "x-ratelimit-reset-tokens": "1m7.66s", "x-ratelimit-reset-requests": "secret-value",
        "retry-after": "8", "x-ratelimit-limit-requests": "1000"})
    result = safe_quota_headers(headers)
    assert result == {"retry-after": 8, "x-ratelimit-limit-tokens": 8000,
                      "x-ratelimit-limit-requests": 1000, "x-ratelimit-reset-tokens-seconds": 67.66}


def test_limit_errors_keep_only_numeric_counts_and_dimension():
    response = httpx.Response(429, json={"error": {"message":
        "Secret organization never-emit; tokens per day (TPD): Limit 200000 Used 199900 Requested 1293."}})
    assert safe_limit_error(response) == {"dimension": "TPD", "limit": 200000,
                                           "used": 199900, "requested": 1293}
    assert safe_limit_error(httpx.Response(503, content=b"never-emit")) == {}


def test_google_structured_quota_retry_has_no_project_subject_or_free_text(store):
    body = {"error": {"message": "never-emit API key or project", "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
            {"subject": "project:never-emit", "description": "never-emit",
             "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
             "quotaValue": "20", "quotaDimensions": {"model": "never-emit"}}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "123.25s"}]}}
    response = httpx.Response(429, json=body)
    assert safe_limit_error(response) == {"retry_after_seconds": 123.25,
                                          "google_violations": [{"dimension": "RPD", "limit": 20}]}
    def handler(request):
        return response
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            provider = Provider("gemini", "fixture-model", "fixture-key", Limits(10, 100, 100000, 100000))
            return await Router(Quotas(store), http, (provider,)).analyze(
                {"earnings-call-facts": ["Revenue increased."]}, time.time()+300)
    result = asyncio.run(run())
    assert "never-emit" not in json.dumps(result.attempts)
    assert Quotas(store).summary()["gemini"]["cooldown_until"] >= time.time()+120
