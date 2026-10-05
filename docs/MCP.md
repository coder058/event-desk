# Read-only MCP

The optional official Python SDK exposes exactly four tools: `get_predictions`,
`get_event`, `get_scoreboard` and `explain`. They read the public HTTP API and
cannot submit competition predictions, call a provider or place broker orders.

```sh
pip install '.[mcp]'
EVENTDESK_READ_ORIGIN=http://127.0.0.1:8000 python -m eventdesk.mcp
```

Use the command as a stdio server in an MCP client. The default origin is the
local API. For Windows, set `EVENTDESK_READ_ORIGIN` in the client's environment.
The only remote origin accepted is the project's HTTPS hostname; its inbound
networking is still blocked. No tool API key or new account is required.

`get_event` and `explain` take `event_id` and an optional `slot` (`s1`–`s5`).
Evidence always belongs to that submission slot. `explain` returns the retained
linear contribution trace and separately labelled AI evidence, never a new
forecast or invented private thoughts. Missing records return an error.

Verified 2026-10-05: actual SDK protocol tests, GET-only mock transport and a
real stdio subprocess reading the deployed zero-event service through its SSH
preview. This is not a public hosted MCP endpoint or an official live prediction.

Quotes returned by tools are untrusted source evidence, not instructions. The
SDK is optional so the competition image does not need an MCP runtime to score.
