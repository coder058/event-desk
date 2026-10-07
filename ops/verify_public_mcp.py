"""Read the real public TLS service through the official MCP SDK; no credentials."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from mcp import Client

from eventdesk.mcp import PublicReadAPI, create_server


async def verify() -> dict:
    origin = "https://52.17.192.36.sslip.io:80"  # SOURCE: externally verified project listener.
    server = create_server(PublicReadAPI(origin))
    async with Client(server) as client:
        tools = (await client.list_tools()).tools
        assert {tool.name for tool in tools} == {"get_predictions", "get_event", "get_scoreboard", "explain"}
        assert all(tool.annotations.read_only_hint and not tool.annotations.destructive_hint for tool in tools)
        observed = []
        for name in ("get_predictions", "get_scoreboard"):
            result = await client.call_tool(name)
            assert not result.is_error
            observed.append(name)
    return {"checked_at": datetime.now(UTC).isoformat(), "origin": origin,
        "sdk_read_tools_verified": observed, "advertised_tools": sorted(tool.name for tool in tools),
        "credentials_used": False, "limits": "In-process SDK over actual HTTPS GETs; no live event to inspect, no stdio recheck"}


if __name__ == "__main__":
    proof = asyncio.run(verify())
    Path("reports/public-mcp.json").write_text(json.dumps(proof, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(proof))
