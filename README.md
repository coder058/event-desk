# Event Desk

**Event Desk: AI agents that read every earnings call and SEC filing as it happens,
predict how the market will react, and are scored live — in the Optiver × Chicago
Booth "Explaining Markets" competition and on our own public scoreboard.**

This is the product objective. Competition infrastructure is under construction;
SEC ingestion and live scoring are not yet operational.

## Pipeline

Signed event → durable queue → official materials → trained local prediction →
best-effort free LLM evidence → frozen prediction → competition acknowledgement.

The local model provides coverage when free APIs are unavailable. Structured
sub-scores make LLM outputs auditable. Evaluation is chronological, and configuration
changes are recorded before the competition begins.

## Status

See [verified progress](PROGRESS.md), [plan](PLAN.md), [decisions](DECISIONS.md)
and [external actions](BLOCKED.md).

[Official competition](https://explainingmarkets.ai/) ·
[Binding rules](https://explainingmarkets.ai/contest-rules)

## Stack

Python, FastAPI, PostgreSQL, Pydantic, scikit-learn, Docker and Caddy.
Gemini and Groq are optional free-tier providers. No trading credentials are required
for competition predictions.

## Limits

No verified live score, measured latency, calibrated win probability or profitability
is claimed. Competition predictions are a research task, not broker executions.
Free APIs and a single existing VPS can fail. Ten scoring days and prospective
event-study outcomes must actually occur before the full project is complete.
