import asyncio

import httpx
import pytest
from mcp import Client

from eventdesk.mcp import PublicReadAPI, create_server


def test_mcp_has_exactly_four_read_only_tools_and_no_write_requests():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        if request.url.path == "/api/predictions":
            return httpx.Response(200, json=[{"event_id": "fixture", "state": "simulated"}])
        if request.url.path == "/api/scoreboard":
            return httpx.Response(200, json={"official_live_score": None})
        assert request.url.path == "/api/events/fixture"
        assert request.url.params["slot"] == "s2"
        return httpx.Response(200, json={"event_id": "fixture", "slot": "s2",
            "state": "simulated", "local_trace": {"kind": "fixture"},
            "analysis_trace": {"affects_prediction": False}})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            server = create_server(PublicReadAPI("http://127.0.0.1:8000", http))
            async with Client(server) as client:
                tools = (await client.list_tools()).tools
                assert {tool.name for tool in tools} == {"get_predictions", "get_event", "get_scoreboard", "explain"}
                assert all(tool.annotations.read_only_hint is True and tool.annotations.destructive_hint is False
                           for tool in tools)
                for name in ("get_predictions", "get_scoreboard"):
                    assert not (await client.call_tool(name)).is_error
                for name in ("get_event", "explain"):
                    result = await client.call_tool(name, {"event_id": "fixture", "slot": "s2"})
                    assert not result.is_error
                    assert result.structured_content["slot"] == "s2"
                assert (await client.call_tool("explain", {"event_id": "fixture", "slot": "s9"})).is_error
    asyncio.run(run())
    assert len(requests) == 4


def test_read_origin_cannot_be_replaced_with_an_unapproved_host_or_embedded_secret():
    for origin in ("https://example.com", "http://169.254.169.254", "http://user:secret@localhost",
                   "http://localhost?api_key=fixture", "http://localhost/private",
                   "http://52.17.192.36.sslip.io:80", "https://52.17.192.36.sslip.io:8800"):
        with pytest.raises(ValueError):
            PublicReadAPI(origin)


def test_verified_explicit_tls_origin_reads_without_redirect_or_auth():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert request.url.scheme == "https" and request.url.port == 80
        assert "Authorization" not in request.headers and "X-API-Key" not in request.headers
        return httpx.Response(200, json=[])
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            api = PublicReadAPI("https://52.17.192.36.sslip.io:80", http)
            assert await api.read("/api/predictions") == []
    asyncio.run(run())
    assert len(calls) == 1
