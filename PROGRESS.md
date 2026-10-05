# Verified progress

## 2026-10-05 — foundation audit

- Read the mission and official rules/docs/FAQ and reference implementations.
- Existing production key authenticated GET /events and GET /archive (HTTP 200).
- Four required secret variable names are present locally; values were not printed.
- Existing archive and Claude scripts inspected; supplied model results not yet reproduced.
- Dublin audit: only protected/unowned AAPL position; no open orders or owned positions.
- New project plan and explicit full completion gate recorded.

- Installed four required keys through SSH stdin at /etc/eventdesk/env: uid 0, mode 600.
- Disabled ten old-project timers and four persistent captures; verified no running
  listed services and no open Alpaca paper orders. Protected AAPL was retained.
- Shutdown record preserves existing failed unit markers and all old journals.
- Fetched scorer pinned by the rules: 501bd3182cd42cf61a727e05bd4b3089b8d1338d.

Remaining: model training/evaluation, durable receiver, HTTPS and actual portal
test. No Event Desk deployment or archived model result is claimed yet.

## 2026-10-05 — local model, receiver and first deployment

- Facts-only model trained on 6,299 scored asset rows from 2025Q4–2026Q2.
- Q3 validation: 2,362 outcome rows; 2,275 in the scorer's surprise-complete common
  sample. Imputed delta R-squared 0.04095315077531125. Enriched candidate 0.022485843848399356.
- Runtime single-event features/predictions matched the evaluated batch model.
- Q3 calendar quarter is closed but API manifest says sealed=false: validation
  provenance is the frozen local file hash; archive corrections remain possible.
- Eleven tests passed locally, including 400 synthetic deliveries processed in
  47.136 seconds. This is simulated plumbing coverage, not competition coverage.
- Ruff and strict mypy passed. GitHub CI 37375707148 passed checks and actual
  keyless Docker Compose signed-fixture end-to-end.
- coder058/event-desk created publicly at commit 3976d36. No owner secrets or model
  archive files were published; exact owner-value scan passed before push.
- PostgreSQL migration and real trained artifact deployed on Dublin. Receiver,
  worker, database and Caddy running; model hash da212d24d1f3bb2c0d8528d62160667f7ca61029e748ca8dac6b5df9a2210bce.
- Caddy obtained HTTPS certificate. Origin health verified over loopback, but
  public 443 times out. No portal test or real competition prediction yet.
- Review found HTTPX INFO logs could expose signed material URLs; suppressing
  transport INFO logs before any real material request. No LLM/blend live claim.

Next: unblock verified public HTTPS while implementing the free-provider router,
quota persistence and structured archive calibration. Phase A1 remains incomplete.
