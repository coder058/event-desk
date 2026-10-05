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

## 2026-10-05 — provider reliability work (not a fitted hybrid yet)

- Gemini 3.1 Flash-Lite produced validated structured scores and exact evidence on
  an archived event in 7.468 seconds using 835 reported tokens. Subsequent archived
  calls included valid results and an actual 503 outage.
- Groq GPT-OSS 120B initially appended array indices to evidence item IDs, which
  strict verification rejected. Constrained allowed item IDs in the output schema;
  two subsequent archive responses passed validation (1,299 and 1,276 reported
  tokens), followed by a real HTTP 429. Provider failures are retained, not hidden.
- Quota reservations and cooldowns now have persistent database schemas and tests.
- Runtime leaves the mission's 30-second submission reserve and never enables
  browsing or an additional/paid provider.
- Review corrected a crash gap: evidence and immutable prediction now commit in
  one transaction. An unapproved blend artifact is rejected; shadow evidence
  cannot change the local percentile without a fitted, approved mapping.
- Sixteen non-load tests passed with strict application typing. LLM code is not
  yet deployed; the current live worker is still local-only. Archive collection
  is insufficient for a fitted hybrid or an LLM performance claim.

## 2026-10-05 — coverage isolation and real load attempts

- Commit 6c99929 passed GitHub CI 37378515533 and deployed provider-budget and
  evidence migrations on Dublin with LLM use still disabled.
- Senior review found an unnecessary deadline risk: unapproved shadow LLM work
  was awaited before submitting local predictions. Replaced this with a separate
  durable post-submission evidence queue, tested for immutable prediction and
  restart recovery. Nineteen non-load tests and strict typing/lint passed locally.
- Real fixture replay attempt one failed on API startup; added an actual readiness
  check. Attempt two failed on an ACK response. Further diagnosis is required;
  neither attempt establishes 400-event coverage. Production remained separate
  with zero received events and a reachable database after cleanup.
- Groq validated one additional current-prompt Q2 sample (1,293 reported tokens),
  then returned 429 with Retry-After 353 seconds. Retained documented numeric
  headers; no error body, owner credential or signed URL was printed.
- Gemini current-prompt archive collection returned 503 and stopped. No fitted
  blend, full LLM evaluation, portal test or official live coverage is claimed.

- Added a single queue dispatcher with eight concurrent processing slots to avoid
  eight independent idle pollers. Fault test held cloud analysis indefinitely while
  24 synthetic predictions completed, including a fitted-mean fallback for malformed
  official facts. Twenty-one non-load tests passed; latest local 400-event plumbing
  replay completed in 39.144 seconds. These are not Dublin load results.
- The next Groq sample validated on Q3 (1,241 reported tokens); subsequent 429 was
  explicitly TPD: limit 200,000, used 199,841, requested 1,457. The account-wide daily
  budget, not the project's minute bucket, is the observed constraint.
- Third Dublin fixture attempt timed out at API readiness during resource contention;
  no successful full replay is claimed. Added health diagnostics before fixture cleanup.
- Dependency-image rebuilds consumed minutes on this VPS. Split Docker dependency
  installation from application packaging so reviewed source edits can reuse layers.

## 2026-10-05 — verified Dublin load and inference; evidence review

- Commit 273c70e passed CI 37380936693 and deployed deadline-isolated optional AI.
- Fourth isolated Dublin fixture attempt passed: 400 ACKs and 400 simulated results
  in 61.132923 seconds. ACK p95 5.048102 seconds, maximum 8.160653 seconds, below
  the official 20-second limit in this test. Concurrent HTTP clients: 16, an
  uncalibrated load choice. Readiness health requests timed out during load;
  production stayed separate, with zero received events after fixture cleanup.
- Read-only Dublin inference benchmark used 2,362 archived Q3 inputs without
  transferring outcomes: cold model load 2,831.785 ms; prediction p50 1.946 ms,
  p95 2.269 ms, maximum 5.754 ms. Maximum prediction difference against the local
  Windows runtime was zero. These exclude HTTP, database and submission time.
- Gemini 3.5 Flash-Lite returned six current-prompt valid archive analyses across
  Q2/Q3; it is an offline candidate, not an approved deployed hybrid. That sample
  is insufficient for a fitted mapping or an advantage claim.
- Review found per-slot receipt locking serialized unrelated events. Changed to
  sorted per-event/per-delivery PostgreSQL advisory keys; real concurrency replay
  will verify the change before it is described as a demonstrated improvement.
- Added persisted worker heartbeats and pre-submission linear-model contribution
  traces. Explanation failures cannot replace a valid prediction. TEST/fixtures
  stay separate from live acceptance/eligibility metrics. Slot-specific detail
  queries prevent evidence from one submission being displayed for another.
- Public HTTPS, the owner's portal test, hybrid calibration, frozen registration,
  EDGAR and future scored days remain incomplete. No live score is claimed.

- Commit 7a34a6c passed CI 37384262617 and deployed the contribution/health views.
  Actual PostgreSQL/HTTP receipt races passed: twenty simultaneous duplicate ACKs
  produced one job/one delivery; twenty new delivery IDs retained one job and its
  first deadline; both changed body and changed focal identity returned HTTP 409.
- Subsequent 400-event Dublin fixture replay completed in 8.470834 seconds, ACK
  p95 586.061 ms, maximum 922.017 ms. Different contention/locking conditions prevent
  attributing the entire speedup to one change; this is one replay, not capacity proof.
- Browser verified real production zero-event state and separately inspected actual
  synthetic pre-submission contributions. Production screenshot retained in docs.
- Senior review found streaming the request body was outside the receipt timer.
  Added one shared guard across body, validation and durable receipt; an injected
  stalled-stream test returns 503 without persisting an event rather than ACKing.

## 2026-10-05 — encrypted backup and recovery drill

- Installed only the Ubuntu age package on the two existing hosts; no account,
  paid plan, kernel upgrade or reboot. Frankfurt cursor-worker remains active with
  its original 18 September start time. Fly Brain source/results were not touched.
- Isolated Frankfurt receive-only key/path restricts command, filename, source IP
  and overwrites; bounded receiver tests passed. Encryption happens on Dublin;
  only ciphertext travels through the dedicated pinned-host SSH connection.
- Initial backup helper failed because Ruff converted timezone.utc into the
  Python-3.11 UTC name, unavailable in Dublin's host Python 3.10. Corrected the
  host-helper compatibility explicitly; the application remains Python 3.12.
- Two actual copies transferred. Hash/decryption checks verified all seven
  archived files; an isolated database restore recovered 006_local_trace with
  zero jobs and deliveries, matching the no-event snapshot. Production was never
  a restore/drop target. Fixed a Windows closed-pipe diagnostic and repeated the
  stream verification successfully. Public receipt: reports/backup-restore.json.
- The hardened systemd service succeeded; nightly timer is active for 04:10 UTC.
  That scheduling choice is uncalibrated. A scheduled future run has not occurred
  yet; the successful manual service invocation does not prove every future copy.
- Remaining recovery limit: the private age identity exists only on Frankfurt.
  Loss of both hosts lacks an offline recovery copy; no full-host recovery time
  or automatic destructive production restore is claimed.
