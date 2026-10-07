import asyncio
import gzip
import importlib
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from eventdesk.llm import Provider
from eventdesk.quotas import Limits


class EndObserverCycle(Exception):
    pass


@pytest.mark.parametrize("entry", ["collect_llm", "probe_llm", "competition", "read_competition_state"])
def test_credential_clients_ignore_ambient_proxy_and_ca_settings(monkeypatch, tmp_path, store, settings, entry):
    """Execute each entry point with real client construction and mock-only HTTP.

    Ambient proxies/CA overrides must not influence credential-bearing requests.
    No provider or competition request leaves this process.
    """
    # PLACEHOLDER: all addresses, timestamps, text, scores and token counts below
    # are deterministic synthetic test inputs, not measured provider performance.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "research"))
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "ops"))
    module = importlib.import_module("eventdesk.competition" if entry == "competition" else entry)
    monkeypatch.setenv("HTTPS_PROXY", "http://ambient-proxy.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "http://ambient-proxy.invalid:8080")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "untrusted-missing-ca.pem"))
    monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "untrusted-missing-ca-dir"))

    def forbidden_proxy_discovery():
        raise AssertionError("Ambient proxy discovery reached a credential client")

    monkeypatch.setattr(httpx._client, "get_environment_proxies", forbidden_proxy_discovery)
    requests = []
    analysis = {"beat_vs_buyside_bar": 1, "guidance_change": 0, "tone": 0, "new_risks": 0,
                "surprise_vs_preview": 0, "confidence": .5,
                "evidence": [{"item_id": "earnings-call-facts", "quote": "Revenue increased."}]}

    def handler(request):
        requests.append((request.method, request.url.host, request.url.path))
        if request.url.host == "api.groq.com":
            assert request.headers["authorization"] == "Bearer fixture-not-owner"
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(analysis)}}],
                                             "usage": {"total_tokens": 1}})
        assert request.url.host == "api.explainingmarkets.ai"
        assert request.headers["x-api-key"] == "fixture-not-owner"
        if request.url.path.endswith("events"):
            return httpx.Response(200, json=[])
        assert request.url.path.endswith("health")
        return httpx.Response(200, json={"webhook_n_2xx": 0, "submission_n_total": 0})

    real_async, real_sync = httpx.AsyncClient, httpx.Client

    def async_client(*args, **kwargs):
        # Construct before substituting transport: the real HTTPX environment/CA
        # initialization is tested, while all subsequent requests stay mocked.
        client = real_async(*args, **kwargs)
        client._transport = httpx.MockTransport(handler)
        return client

    def sync_client(*args, **kwargs):
        client = real_sync(*args, **kwargs)
        client._transport = httpx.MockTransport(handler)
        return client

    monkeypatch.setattr(httpx, "AsyncClient", async_client)
    monkeypatch.setattr(httpx, "Client", sync_client)

    if entry == "competition":
        monkeypatch.setattr(module.Settings, "from_env", lambda: replace(settings, fixture_mode=False))
        monkeypatch.setattr(module, "Store", lambda _: store)

        async def finish_cycle(_):
            raise EndObserverCycle

        monkeypatch.setattr(module.asyncio, "sleep", finish_cycle)
        with pytest.raises(EndObserverCycle):
            asyncio.run(module.run())
        assert requests == [("GET", "api.explainingmarkets.ai", "/v1/events"),
                            ("GET", "api.explainingmarkets.ai", "/v1/health")]
        assert store.competition_overview()["submissions"]["s1"]["collector"]["state"] == "observed"
    elif entry == "read_competition_state":
        monkeypatch.setattr(Path, "home", classmethod(lambda _: tmp_path))
        secret_dir = tmp_path / ".eventdesk"
        secret_dir.mkdir()
        (secret_dir / ".env").write_text("EM_API_KEY=fixture-not-owner\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        module.main()
        assert requests == [("GET", "api.explainingmarkets.ai", "/v1/events"),
                            ("GET", "api.explainingmarkets.ai", "/v1/health")]
    else:
        monkeypatch.setenv("DATABASE_URL", "postgresql://fixture-not-used")
        monkeypatch.setattr(module, "Store", lambda _: store)
        # PLACEHOLDER: fixture budget permits one mocked call, not a claimed API quota.
        provider = Provider("groq", "openai/gpt-oss-120b", "fixture-not-owner", Limits(1, 1, 100000, 100000))
        monkeypatch.setattr(module, "providers_from_env", lambda: (provider,))
        record = {"event_id": "fixture", "event_datetime": "2026-04-01T12:00:00Z",
                  "items": [{"id": "earnings-call-facts", "content": ["Revenue increased."]}]}
        archive = tmp_path / "2026Q2.jsonl.gz"
        with gzip.open(archive, "wt", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
        output = tmp_path / "output"
        if entry == "collect_llm":
            monkeypatch.setattr("sys.argv", [entry, "--quarter", "2026Q2", "--provider", "groq", "--count", "1",
                                             "--archive-dir", str(tmp_path), "--output-dir", str(output)])
            asyncio.run(module.main())
            rows = [json.loads(line) for line in (output / "llm-groq-2026Q2.jsonl").read_text().splitlines()]
        else:
            monkeypatch.setattr("sys.argv", [entry, "--archive", str(archive), "--output-dir", str(output)])
            asyncio.run(module.run())
            rows = json.loads((output / "provider-probe.json").read_text())
        assert len(requests) == 1 and requests[0][:2] == ("POST", "api.groq.com")
        assert rows[0]["analysis"] == analysis
