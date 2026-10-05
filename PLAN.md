# Event Desk execution plan

Mission accepted 2026-10-05. This replaces the AI OCaml Bot backlog.
Competition deployment and a real portal test have priority before 10 October.
Work remains inline. Record verified work, not elapsed time, in PROGRESS.md.

## A0 — foundation

- Read binding rules, webhook documentation and official implementations.
- Create coder058/event-desk with scoped commits, tests and secret scanning.
- Install existing keys at /etc/eventdesk/env, root-owned mode 600.
- Freeze only the old project's services after verifying owned positions and orders.
- Document shutdown without deleting journals, data or code.

## A1 — durable local-first receiver

- PostgreSQL migrations, unique delivery/event keys, durable queue and leases.
- Raw-byte HMAC verification against official vectors; bounded ACK path.
- Trained local artifact with provenance and identical offline/runtime features.
- Persist prediction before POST; retry the identical payload after uncertain responses.
- HTTPS through Caddy on the existing VPS; database stays on the internal network.
- Give owner the verified URL, record actual portal delivery and submission outcome.

## A2 — measured AI layer

- Reproduce facts-only baseline on closed archive quarters with the official scorer.
- Compare facts/preview/options/missingness using frozen chronological splits.
- Gemini/Groq free-only router with persistent rate budgets and deadline reserve.
- Validate sub-scores and verbatim evidence; archive/provider runs must be recorded.
- Fit a blend using training labels and LLM outputs; no invented blend coefficients.
- Fault/restart/concurrent duplicate tests and 400-event busy-day replay.

## A3 — freeze and operations

- Accurate model card, preregistration/configuration hashes and changes log.
- Deadline/coverage alerts locally unless optional channels become configured.
- Nightly database/model backups on the existing Frankfurt host in an isolated directory.
- Monitor official health; API acceptance alone is not proof of score eligibility.

## B1–B3 — event research

- EDGAR 8-K, Form 4, Schedule 13D and Defense contracts with identified UA/rate limits.
- Hash-addressed raw evidence, acceptance timestamps and typed quoted extraction.
- Freeze extractor before prospective 1/5/20-day sector-adjusted event studies.
- Placebos, uncertainty intervals and honest unavailable outcomes.
- Add only validated external pre-cutoff features in a separately logged version.

## C1 — paper event portfolio

- Reuse hardcoded Alpaca paper origin, ownership journal and reconciliation.
- Long-only small equal notional; holding period/exposure/daily loss/drawdown gates.
- Exact fee attribution; no live path and no profitability claims from paper fills.

## D1 — public product

- Readable predictions/evidence, source/status, coverage/fallback/latency and architecture.
- Official leaderboard link; no fabricated running score before official outcomes exist.
- Event-study and paper pages explicitly pending until evidence exists.
- Read-only API/MCP; README at most 120 lines; fixture compose without keys.

## Full completion gate

100% eligible events for ten consecutive scoring days, EDGAR daily with a published
prospective event study, live public page/README, green CI, no committed secrets,
and a ten-line factual summary with limits. Scoring starts 12 October: this gate
cannot truthfully be met during the current development session.
