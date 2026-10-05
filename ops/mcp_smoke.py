"""Exercise the actual stdio SDK against retained public data; GET requests only."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def main() -> None:
    root = Path(__file__).resolve().parents[1]
    transport = StdioServerParameters(command=sys.executable, args=["-m", "eventdesk.mcp"],
        cwd=str(root), env={"PYTHONPATH": str(root / "src"), "EVENTDESK_READ_ORIGIN": "http://127.0.0.1:8000"})
    async with Client(transport) as client:
        tools = (await client.list_tools()).tools
        expected = {"get_predictions", "get_event", "get_scoreboard", "explain"}
        if {tool.name for tool in tools} != expected:
            raise RuntimeError("Unexpected MCP tool inventory")
        results = {}
        for name in ("get_predictions", "get_scoreboard"):
            result = await client.call_tool(name)
            if result.is_error:
                raise RuntimeError("Read-only MCP smoke failed")
            results[name] = result.structured_content
        missing = await client.call_tool("explain", {"event_id": "nonexistent-protocol-smoke", "slot": "s1"})
        if not missing.is_error:
            raise RuntimeError("MCP invented a missing event")
        print(json.dumps({"transport": "actual_stdio", "tools": sorted(expected),
            "public_results": results, "missing_event_is_error": missing.is_error,
            "limits": "Read-only localhost production records; no submission, provider or broker request"}))


if __name__ == "__main__":
    asyncio.run(main())
