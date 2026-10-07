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

## 2026-10-05 — initial prediction declaration, not live eligibility

- Declared the initial facts-only method before prospective scoring. Frozen
  configuration/source/scorer/artifact/prompt hashes are in PREREGISTRATION.md.
  Q3's previously inspected, unsealed status and the lower enriched result remain
  explicit; generative samples have not approved a hybrid or a win probability.
- Added startup mismatch guards and verification before joblib deserialization.
  Hashing/deserializing the same byte buffer avoids a pathname replacement gap.
  Optional missing provider keys cannot prevent the trained local fallback.
- Configuration hashes are stored atomically with immutable predictions. Tested
  mismatched artifact/source/provider pins and rejection of an undeclared blend.
  Pending: actual deployment/startup verification of these new guards.
- Latest collection added one valid Groq Q2 analysis (1,190 tokens), then a TPD
  429 (used 199,245 of 200,000; requested 1,221; Retry-After 202 seconds). Gemini
  3.5 returned 429 with no recognized numeric dimension. Attempts are retained;
  no amount of repeated requests is treated as new calibration evidence.

- Declared-config worker startup verified on Dublin at 329265b, real artifact and
  schema 007. Before any received event, comparison against public Git found the
  configuration's working-copy CRLF produced a different raw hash than Git LF.
  Normalized only line endings in the hash and tested both encodings; updated
  the declaration to the public-file hash. Predictions/features did not change.

## 2026-10-05 — trained-artifact replay and deadline resilience

- Production 7b20bb0 passed CI 37386883112, schema 007 and the canonical declaration
  hash 7e15d626651b578a1686c90b1ee1c473f29f9355ef6aa1b4c866ee520f538cd1.
- Replayed 400 chronological Q3 official material bundles with the actual trained
  artifact in an isolated HTTP/PostgreSQL fixture. No outcomes were transmitted;
  no competition/provider/broker request occurred. All 400 ACKs and simulated
  results completed in 66.416155 seconds; maximum ACK 1,700.730 ms / p95 823.359 ms.
  This measures that replay, not accuracy, live eligibility or maximum capacity.
  Fixture containers were removed, volumes retained, production remained at zero.
- Serial profile: prediction p50 2.612 ms / p95 3.851 ms; explanation p50 96.813 ms
  / p95 176.131 ms. Rebuilding static vocabulary metadata dominated explanation work.
- Paired alternating-order comparison on the same host/400 inputs: original
  explanation p50 100.345 ms / p95 175.565 ms; cached sparse explanation p50
  2.735 ms / p95 4.195 ms. Term names matched, maximum percentile difference
  1.11e-16 and displayed-math difference 5.55e-17. Cold-load timings had unequal
  import/page-cache warmth and cannot be compared as controlled cold starts.
- Prediction function, feature builder and trained artifact remain declared and
  unchanged. Tests verify sparse contributions and no per-event vocabulary rebuild.
- Expired jobs are drained transactionally rather than sleeping once per expired
  event. Tests put 400 expired jobs before a valid job, for both submission and shadow.
- Material DNS/streaming share the download budget and leave the required 30-second
  submission reserve. A late queued event explicitly uses the fitted training mean,
  not invented text evidence; deadline/DNS/body stall tests verify the degradation.
- Pending: deployed verification and a repeat trained-artifact replay of these changes.
  Public HTTPS/portal delivery remain blocked; no live coverage or hybrid is claimed.

- The full SQLite replay exposed write-lock contention after adding transactional
  expiry cleanup. All fixture write transactions now share the same exclusion;
  PostgreSQL's transaction/row locks remain unchanged. SQL exception parameters
  are hidden so private material cannot leak through an unexpected database error.

## 2026-10-05 — optional read-only MCP

- Added the official SDK's four read-only tools over public HTTP records. Protocol
  tests check exact tool inventory, read-only annotations, GET-only behavior,
  slot-correct evidence and rejection of unapproved origins/invalid slot arguments.
- Real stdio subprocess smoke read the actual deployed zero-event service through
  localhost; a missing event returned an error. Expected errors use SDK ToolError,
  avoiding traceback noise and invented fallback records.
- Optional SDK setup is documented in docs/MCP.md. This is a stdio server, not a
  claim that a public HTTPS MCP service or any official scored event exists.

- Commit 2e8792f passed CI 37389255947 and deployed on Dublin. Trained-model
  replay then completed 400 ACKs/simulations in 10.625704 seconds, maximum ACK
  1,248.454 ms. The report metadata helper failed after replay due to nested
  escaping. Repaired it; recovered the already-written aggregate and read hashes
  from the unchanged production worker, verifying public source and matching
  image ID. The report states this metadata-recovery boundary explicitly.
- Added three more valid Groq Q2 analyses (1,282 / 1,210 / 1,184 tokens). These
  small samples do not justify a blend. Clarified that Q2 calibration needs local
  predictions from a Q4/Q1-only model, not the in-sample deployed through-Q2 model.

## 2026-10-05 — local observability, deployment still to verify

- Manual OpenTelemetry spans use an allowlisted local exporter, with no network
  endpoint, source text, signed URL, raw exception or environment-value export.
  Actual SDK tests verify parent/child correlation and exception-message exclusion.
- Independent host monitor logs alert transitions and a daily cumulative summary,
  distinguishing worker, deadlines, rejected/expired work and backup transfer age.
  An origin-side HTTPS request does not verify external inbound networking.
- Docker log rotation is bounded. Operational cadence/retention/age thresholds are
  uncalibrated choices, labelled in code. Telegram/Langfuse remain optional.
- Pending: deployment, actual local spans and timer behavior, latest-schema backup.

## 2026-10-06 — deployed observability and provider cooldown evidence

- Source 6f9cdfc passed CI 37403411478 and deployed with schema 007 and the same
  declared model/configuration. Production still had zero received events.
- Independent host timer is active. Its actual state correctly reports only
  `https_path_unverified`: worker heartbeat and backup transfer are healthy;
  origin-side HTTPS and external inbound verification are still unavailable.
- An isolated fixture process inside the deployed image exported correlated
  job/inference OpenTelemetry spans. Source text was excluded and no network
  request occurred. Evidence: reports/dublin-telemetry-fixture.json. This was
  not a production event or a full distributed receipt-to-provider trace.
- Actual encrypted backup/isolated restore verified nine files and schema
  007_configuration_hash, with zero jobs/deliveries matching the snapshot.
  Production was not a restore target. The nightly scheduled run is still pending;
  reports/backup-restore.json records the manual run and measured ciphertext hash.
- Groq rejected the next Q2 attempt: TPD 200,000, used 199,788, requested 1,195;
  Retry-After 425 seconds. Gemini 3.5 rejected the next attempt with RPD 500 and
  RetryInfo 77,956 seconds. These are actual response fields, not estimates of
  remaining quota or an inferred limit for the deployed Gemini 3.1 model.
- Added strict numeric-only parsing of Google's QuotaFailure/RetryInfo, with
  project IDs, model dimensions and free text excluded. Tests verify persistent
  cooldown respects the returned duration. No prompt, features or prediction
  function changed; the small valid sample still does not justify a blend.

## 2026-10-06 — official read-only calendar/counters

- Source b5f105d passed CI 37404395942 and deployed; trained worker heartbeat,
  unchanged model/configuration and zero received events were verified afterward.
- Authenticated GET /events and GET /health returned 2,970 scheduled entries,
  zero rolling delivery/submission counters and no reported portal-test prediction.
  The returned calendar is a current partial schedule, not official scored coverage.
- Added a separate production metadata observer with no POST route. Tests verify
  GET-only requests, fixture isolation, bounded reads, ignored unknown fields,
  Central-time scoring boundaries and unavailable eligibility. Changed calendars
  are versioned; failed observations preserve the last complete snapshot.
- Added append-only schema 008 observations, dashboard aggregates and independent
  alerts for stale/failed observations and official reported delivery failures.
  Full local suite: 47 passed in 69.27 seconds; strict typing passed in 15 modules.
  These changes still need deployment and actual PostgreSQL/browser verification.

## 2026-10-06 — chronological local calibration component

- Built a separate Q4/Q1-only facts model from 4,239 rows with the inherited fixed
  settings, and 2,060 out-of-training-sample Q2 predictions. Official scorer used
  1,996 surprise-complete rows; imputed delta R-squared 0.008100532382788295.
  Actual hashes and dataset provenance: reports/calibration-local.json.
- Private artifact/predictions remain outside deployment and cannot silently
  overwrite retained evidence. The deployed through-Q2 model hash was unchanged.
  This closes the in-sample local-feature problem for Q2 blend fitting, not the
  insufficient LLM sample or final hybrid validation.
- Two more current-prompt Groq Q2 analyses passed (1,253 / 1,235 tokens), then TPD
  429: limit 200,000, used 199,730, requested 1,212; Retry-After 407 seconds.
  That attempt is retained and collection stopped instead of bypassing the limit.

- The official observer is now deployed at a3a49d8: actual PostgreSQL schema
  008, one retained calendar version/health observation, collector running without
  OOM, and the unchanged trained prediction worker remained healthy. Host monitor
  was updated and still reports only the unresolved HTTPS path.
- Browser verification showed calendar/counters and no fabricated coverage or
  events. Capacity grouped in Central shows a peak of 534 on November 5, versus
  535 in the earlier UTC-date diagnostic: timezone grouping changes that count.
  The declared display convention does not determine scoring eligibility.
- Browser/UTF-8 code-point comparison exposed a pre-existing Windows encoding
  corruption since the older dashboard version. Recovered symbols from the actual
  bytes; the cosmetic fix still needs deployment and browser verification.

## 2026-10-06 — real PostgreSQL outage/reserve drills

- Cosmetic recovery is deployed at 620443b, CI 37405439200 passed; browser symbols
  and the actual official-observation panel were verified. docs/dashboard.png is
  a capture of the zero-event deployed service through the existing SSH preview.
- Reserve-only drill: 400 events seeded with 30 seconds remaining completed 400
  simulated submission responses in 6.743447 seconds. No material GET was attempted;
  all retained `materials_skipped_deadline_reserve` with the actual fitted mean.
- Full-source-outage drill: 400 synthetic events / real worker and isolated PG
  database completed 400 simulated responses in 273.067230 seconds. 144 material
  reads stalled; 256 were skipped as the reserve approached. All used the fitted
  mean. Mock transport could not access the public network; database was disposed.
  Reports: dublin-material-reserve.json and dublin-material-source_outage.json.
- This closes the tested material-outage queue scenario, not a live network/ACK
  latency guarantee or model accuracy claim. An external submission outage can
  still prevent delivery; constant mean outputs provide no event-specific skill.
- Groq supplied one additional current-prompt Q3 analysis (1,428 tokens), then TPD
  429: limit 200,000, used 199,736, requested 1,319; Retry-After 456 seconds.
  There is still insufficient chronological evidence for hybrid deployment.

## 2026-10-06 — source evidence foundation

- Added content-addressed immutable bytes, strict capture/acceptance/cutoff times
  and exact quotes verified against reread source bytes. Synthetic tests check
  concurrency, corruption, traversal, later capture and forged text attribution.
- This is initial raw UTF-8 quote/storage support, not a daily EDGAR collector,
  full HTML/PDF/XML parser, event study or LLM extraction. Those limits and the
  missing identified SEC contact are explicit in docs/EVIDENCE-BOUNDARIES.md.

## 2026-10-06 — submission retry and public response boundaries

- Source 5580202 is deployed; CI 37406542625 passed. Read-only verification
  found schema 008, four retained observations, running observer and a recent
  unchanged trained-model worker heartbeat. Zero official events and TESTs.
- The initial probe used nonexistent `/health` (404); `/healthz` and the actual
  read-only verification succeeded. This was a probe mistake, not a service outage.
- Added integer/date Retry-After scheduling without changing the durable outbox;
  delays that cannot fit before the original deadline expire, rather than repost.
- Public event/listing responses now derive acknowledgement status from our own
  ledger instead of reflecting arbitrary server JSON. Private response evidence
  remains retained; HTTP 201 still does not prove score eligibility.
- SQLite calibration settlement now uses the existing write guard. Tests exercise
  concurrent cooldown updates and prevent a shorter result overwriting the maximum.
- Focused retry/router/shadow/scoreboard checks initially passed 14 tests. The
  complete suite then passed 54 tests in 52.27 seconds, with strict typing in
  17 modules and lint clean. No prediction code or trained artifact changed.

## 2026-10-06 — source checkpoints and initial Form 4 extraction

- Submission retry/public-boundary changes deployed at 0454c51; CI 37444275113
  passed. Model and configuration hashes stayed unchanged; zero official TESTs.
- New source capture manifests and batch/cursor updates commit atomically after
  retained-byte verification. SQLite tests exercise duplicate races, cross-feed
  identity, restart, stale writers, cutoff exclusion and rollback on cursor failure.
  The new PostgreSQL race fixture and schema 009 await actual deployment/CI.
- Initial Form 4/4-A Table I extractor retains exact original UTF-8 XML quotes,
  filing-level 10b5-1 flag, joint owner identifiers and reported transactions.
  Numeric/code interpretations follow SEC Ownership XML 5.5; DTDs are rejected.
  It does not infer tax motives, per-row plan status, materiality or trading signals.
- Full local suite passed 63 tests in 80.17 seconds; strict typing passed in
  19 application modules; lint and exact owner-secret scan passed. No daily SEC
  collector, actual filing extraction or event study is claimed.
- First actual nightly backup ran at 04:10 UTC: encrypted file
  eventdesk-20261006T041004Z.tar.gz.age was verified on Frankfurt and restored
  into an isolated database. Nine archived files, schema 008, one calendar and
  eleven observations were recovered. Production was never a restore target.
- Groq supplied three additional valid current-prompt Q2 analyses, then the
  collector stopped at its persistent local admission limit, not a new server
  error. The current small Q2/Q3 sample still cannot justify hybrid deployment.
- Read-only official snapshot retained 13 calendar versions and 45 observations;
  latest calendar had 2,955 entries and peak 535 on November 5 in Central time.
  Schedules change; measured 400-event drills do not prove 535-event outage capacity.

Remaining: public inbound HTTPS/portal TEST, adequate chronological blend evidence,
PostgreSQL source verification, identified live SEC reads and future scored coverage.

## 2026-10-06 — bounded submission attempts

- Source checkpoint/ownership commit f001afe passed CI 37446846282. Actual
  PostgreSQL fixture verified eight duplicate attempts, four cross-feed commits
  and one retained capture; no external SEC request occurred.
- Submission now bounds the whole connection/header/body attempt by the inherited
  15-second budget and original deadline. A received HTTP 201 remains an observed
  acknowledgement even if its body stalls, is malformed/nonfinite or exceeds the
  labelled 1 MiB operational cap; it is not reposted for a body parsing failure.
  HTTP 201 is still not proof of eligibility. Full valid response stays private.
- Fault tests distinguish a stalled pre-header POST (uncertain, same immutable
  outbox on retry), a stalled acknowledged body (no retry), and rate-limit headers
  with a stalled irrelevant body (schedule Retry-After without reading it).
- Initial oversized pytest parameter generated a Windows path-too-long setup
  error; explicit short test IDs fixed that fixture issue. Focused checks passed
  18 tests, full suite 71 tests in 86.77 seconds, strict typing/lint/secret scan passed.
- These changes await deployment and do not establish live network coverage.

## 2026-10-06 — PostgreSQL verification and observed-peak outage replay

- Source 5842a4f passed CI 37447596380 and deployed on Dublin. Actual schema 009,
  unchanged model/configuration and recent prediction-worker heartbeat verified.
- A newly created disposable Dublin database ran all Alembic migrations and the
  source concurrency fixture: eight duplicates, four feeds, one capture. It was
  dropped afterward; production was not a test target.
- Replayed the retained calendar's observed 535-entry peak with complete mock
  material outage: 535 simulated POST acknowledgements in 275.600637 seconds.
  144 reads stalled and 391 skipped as the reserve approached; every prediction
  used the fitted training mean. No public request, actual ACK benchmark or live
  accuracy/eligibility claim follows. Workload provenance is in the new report;
  the earlier 400-event evidence was preserved.
- The old local preview tunnel had stopped. Restored SSH forwarding; Edge loaded
  the actual deployed dashboard with recent worker heartbeat. The in-app browser
  continued to reject loopback access, so verification used Edge.

## 2026-10-06 — quota-aware archive collection and provider body boundaries

- Added read-only next-admission computation from persistent rolling windows and
  cooldowns; it is not an account-wide quota guarantee or a reservation. The
  actual router still reserves transactionally before every request. Research
  can wait within an explicit caller budget for local windows; provider outages
  and server cooldowns remain stops. Gemini was not retried during its cooldown.
- Actual bounded Groq run appended 30 valid Q2 analyses; current-prompt Q2 cohort
  reached 42 unique events. Q3 collection is in progress, not a completed result.
- Provider calls now have total time/body bounds and recheck remaining time after
  admission. Invalid token-usage counters cannot create quota credits.
- Initial real Q3 call exposed a new double-decompression error in the streaming
  implementation. A gzip regression reproduced it, then passed after removing
  encoding/length headers from the already decoded response reconstruction.
  The same archived Q3 event subsequently produced valid evidence; the failed
  attempt stays retained. No production prediction or prompt changed.
- Prepared fixed chronological exploratory blend fitting with exact archive/quote
  joins, Q4/Q1-only Q2 local features, private immutable evidence snapshots and
  leave-one-event-out sensitivity. It writes deployment_approved=false only.
  No hybrid evaluation result or deployment approval is claimed yet.

- Final local verification for the bounded collection/provider changes: 84 tests
  passed in 86.04 seconds, strict typing in 19 modules, lint/owner-secret scan clean.
  Gzip reproduction failed before the fix and passed afterward; real Groq Q3
  analyses subsequently validated. No prospective LLM advantage is asserted.
- Workload provenance review found the health-report file was replaced by a later
  probe. Verified the original 535-entry calendar observation directly in the
  append-only production database and recorded that proof; original full report
  bytes were not retained. Future workloads now snapshot report bytes before a run.
- Existing local AWS CLI/SDK, credential files and AWS credential environment names
  were absent. No credential contents were read or additional account created.
  The already documented owner AWS login remains needed for inbound HTTPS review.

## 2026-10-06 — actual structured-AI evaluation and source checkpoint review

- CI 37450534423 passed for c69209b; deployment verified schema 009, recent worker
  heartbeat, unchanged trained model/configuration and local-only flags. Official
  rolling counters still show no webhook/test/prediction. This is not live readiness.
- Groq collection stopped on a real daily-token 429, retaining that failed attempt.
  Current-prompt validated cohorts are 42 Q2 and 28 Q3 events. No limit bypass.
- Ran the prepared fixed chronological blend probe once. Training used Q4/Q1-only
  local features; Q3 evaluation used the deployed through-Q2 local artifact.
  Exact evidence snapshots/hashes remain private; aggregate report is public.
  Full imputed ΔR²: local 0.04095315077531125; AI-only 0.000300660765378602;
  blend 0.03871855275695035. Paired scorer rows: 25, not all 28 response events.
  Blend also underperformed local there. No deployment approval; no LLM advantage.
- Self-review found caller-owned nested checkpoints could mutate after hashing,
  and existing batches were returned without digest/capture revalidation. Added
  detached finite-JSON checkpoint admission and retained-batch/capture verification
  before cursor reads, retries or extensions. Tamper and mutation checks passed
  in the focused 15-test run. Full suite passed 93 tests in 86.99 seconds;
  strict typing/lint and owner-secret scan passed. Actual PostgreSQL verification
  remains to run for this change. An initial full-test shell call used a mistyped
  working directory and never launched; the corrected command produced that result.

- Source bba95e6 passed CI 37512196177 and deployed on Dublin. Actual worker/
  observer heartbeat and schema 009 verified, unchanged local-only model/config.
  A fresh disposable PostgreSQL database passed eight duplicate/four cross-feed
  attempts and one retained capture; cleanup completed, zero external requests.
- The app goal state subsequently returned `paused`, with 16,548 seconds of active
  recorded work (4h35m48s). This is below the requested eight active hours, regardless
  of wall-clock elapsed time. Asked the owner whether to resume; completed only
  the already initiated deployment verification while that reply is pending.
  No completion declaration or additional SEC implementation follows from this pause.
  Next feasible work is the identified/bounded SEC transport and typed ingestion;
  public HTTPS/portal test and SEC contact still need the documented external inputs.

## 2026-10-07 — resumed goal and isolated HTTPS path

- Goal status returned active. Worktree started clean; be6efaf/bba95e6 CI green.
  Actual Dublin worker/observer remain healthy with the unchanged local-only
  configuration. Official counters still record no portal test or delivery.
- Rechecked external 443: connection timeout; existing AWS tab remains signed out.
  Prepared TLS passthrough on the already accessible public 80 path with official
  HAProxy 3.2, preserving Caddy certificate management and plaintext ACME routing.
  No firewall, account, certificate validation or owner credentials are bypassed.
- Actual loopback-only prototype passed verified certificate/health/401/308 checks.
  Earlier attempts failed: unreadable mode-600 static configuration under the
  unprivileged image, then transient cold-start EOF. Corrected static file mode
  and bounded readiness retries; failed diagnostics stay private. Original public
  listeners were untouched during these probes; every temporary proxy was removed.
- Added a keyless Compose TLS fixture for exact signed unicode/whitespace bytes,
  duplicate receipt, modified-body rejection and simulated worker outcome. This
  integration check has not passed yet; public cutover waits for its CI result.
  Production proxy limits are labelled operational guesses, not capacity claims.

- Signed TLS fixture passed CI 37613092682 for d641b50: synthetic durable ACK
  7.452 ms, duplicate ACK, altered-body 401, redirect and simulated completion.
  This is one fixture event, not official coverage or live end-to-end latency.
- Deployed d641b50 after saving the exact prior ingress files privately for rollback.
  External probe at 11:25:53 UTC verified TLS 1.3/certificate, production health 200,
  unsigned webhook 401 and plaintext redirect 308 on the public port-80 TLS route.
  Existing model/configuration stayed unchanged, local-only, with recent worker
  heartbeat. Browser verified the real page and zero official observations.
- Installed the matching independent monitor: no active alerts; external proof
  and origin HTTPS checks pass. Standard 443 remains unreachable. The owner was
  given the exact HTTPS URL and the existing portal's empty Webhook field; no
  official test has been sent and portal acceptance of this port is not inferred.
- Verified the October 7 encrypted nightly backup (1,513,460 bytes): all nine
  archive members passed their hashes, schema 009 restored into a new disposable
  database, 48 calendar versions/156 observations, zero deliveries/jobs. The
  production database was not overwritten; the temporary database was removed.

- Bounded Groq collection added 17 valid Q3 analyses, then stopped on a quote that
  was not verbatim. Invalid output and usage were retained. Verified exact current
  cohorts: 42 Q2 and 45 Q3. No refit, new score or blend approval follows from this.
- Added immutable one-time legacy quota import, migration 010 and shared PostgreSQL
  research collection. Duplicate imports/cooldown preservation/pending-token charge
  checks passed; the stopped source snapshot contains 114 usage rows. Local checks:
  98 tests passed in 97.09 seconds, strict typing in 20 modules and lint clean.
  An initial literal-return typing check failed and was corrected; no external
  research calls used the new path yet. Actual PostgreSQL races/deployment remain
  to verify, so shared-budget operation is not claimed yet.

- CI 37615557536 passed the actual PostgreSQL quota race: four duplicate imports
  committed once; two simultaneous runtime reservations fit the remaining synthetic
  budget, two were denied. No provider request was made by that fixture.
- Deployed c95438c/schema 010 on Dublin; imported the sealed 114-row legacy ledger
  and verified an identical second import returned false. Both real free providers
  subsequently returned valid archived analyses through this shared ledger. Local
  prediction/configuration hashes stayed unchanged; public HTTPS still verifies.
- Added retained-JSON SEC discovery with acceptance timezone/CIK/accession/path/
  array-integrity checks. Ten synthetic parser cases passed, strict typing/lint
  passed. This is recent metadata discovery, not daily ingestion or verified filing
  bodies. External collection remains disabled until the documented contact exists.

- Real shared-ledger collection completed ten additional valid Groq Q3 analyses
  and three valid pinned Gemini Q2 analyses. Retained the exact appended private
  bytes locally. Current verified cohorts: Groq 42 Q2/55 Q3; Gemini 3 Q2.
  The initial negative blend/weights remain unchanged and unapproved.
- Backup review found ingress/private research files were omitted, and hashes were
  taken before rereading live files into the archive. Added explicit project files
  and stable staging copies that reject mutation; restore receipts now publish
  only after test-database cleanup and match the exact latest ciphertext.
  Six focused snapshot/monitor checks passed; actual expanded backup/restore remains
  to verify before claiming those new artifacts are recoverable.

- The expanded backup failed at the restricted receiver: new research loops reused
  the ciphertext filename variable. Receiver rejected the command with ValueError;
  the previously verified backup stayed intact. Metadata-only diagnostics exposed
  no credentials. Renamed loop variables and added a full mocked dump/encryption/
  send regression, not just helper tests. Seven focused checks now pass. Failed
  encrypted local artifacts are retained; none was reported as transferred.
- CI then caught Linux-only double-mapping of temporary paths in the new mocked
  backup test (112 checks passed, that test failed). Limited path substitution to
  the declared host roots; this was a fixture bug, not a second production change.

- Corrected source 693cda4 passed CI 37619622647. The expanded encrypted backup
  actually transferred and restored into an isolated database: 17 archive files
  verified, schema 010, 49 calendar versions/205 observations and zero deliveries.
  Production was not overwritten; monitor verified the exact latest ciphertext.
- Continued under the owner's four-hour repair/optimization goal. Current HTTPS
  health verifies a recent worker and unchanged local model/configuration, with
  LLM and hybrid disabled and zero TEST events. Portal URL is prepared but not
  saved; the owner still performs the final portal actions. Useful independent
  work remains: finish SEC transport verification, enable safe post-submission
  evidence, and add a clearly separate keyless event walkthrough/public case study.
- Local lint and strict typing passed in 22 modules. The first focused test call
  named a nonexistent backup test and did not run; corrected selection follows.
- Corrected focused selection passed 26 transport/discovery/backup/monitor tests.
  SEC source e75d409 is published; actual PostgreSQL gate verification is running
  in CI, not yet asserted passed.
- Found the public MCP allowlist still rejected the verified TLS port 80. Added
  only that exact project port (plaintext/public arbitrary ports still rejected).
  Three MCP checks passed; actual official SDK read predictions/scoreboard over
  public verified HTTPS without credentials. No live event explanation could be
  verified because there are no events. Evidence: reports/public-mcp.json.
- SEC source e75d409 passed CI 37644836771: 122 tests plus actual PostgreSQL
  single-reader exclusion and durable cooldown. No external SEC calls occurred.
- Initial walkthrough generated a real fitted-mean fallback: the fictional
  preview was incorrectly supplied as a list instead of the official string
  schema. Its mathematical-trace test failed rather than silently publishing a
  successful-looking example. Corrected the fixture input; predictor unchanged.
- Corrected walkthrough runs the signed receiver and actual trained model in a
  new disposable SQLite database, without network calls. Receipt, duplicate,
  changed-signature and conflicting-body outcomes are measured (200/200/401/409).
  The numeric contribution trace matches its persisted simulated prediction.
  Three walkthrough tests verify the computation, refusal to overwrite an existing
  database and separation from the empty live ledger; a mislabeled accepted demo
  is rejected. Eleven delivery/local-trace checks also passed in 57.00 seconds.
- Browser reviewed all six desktop walkthrough steps, including source text,
  actual fitted term contributions, hashes, simulation result and absent LLM
  evidence. Screenshot docs/walkthrough.png retains the verified computation.
  Added a public engineering case study and dashboard entry point. Deployment
  remains pending the matching CI; no official events or new score were invented.
- Retrieved the completed private provider evidence and verified shared quota
  metadata read-only: one sealed import, 26 Gemini and 111 Groq usage rows. Those
  rows include attempts and legacy records, not validated-event counts or available
  account capacity. Prompt/model-specific cohorts still require exact validation.
- Walkthrough source 8d0c6c0 passed CI 37646673348. Public MCP source f157aec
  also passed CI 37645113686. Both await the consolidated Dublin deployment.
- Prepared production post-submission evidence enablement with an empty blend
  path and the existing provider pins. Added startup enforcement of the declared
  evidence permission and immutable first completion/identical retries for shadow
  traces. Ambient proxy routing is disabled for credential-bearing HTTP clients.
  Twenty-seven freeze/blend/dispatcher/router/isolation checks passed; strict
  typing/lint passed. Runtime flags are not yet claimed enabled before deployment.
- Current-prompt record counts are Gemini pinned 3.1 Flash-Lite: 13 Q2; Groq
  pinned gpt-oss-120b: 42 Q2/55 Q3. Earlier model/prompt files are distinct and
  excluded. This count does not evaluate a new blend or establish predictive skill.
- Source 104d088 passed CI 37647441702. Prepared an isolated real-provider smoke:
  actual worker/shadow code, fictional inputs, disposable SQLite event book,
  mock official GET/POST, and the deployed PostgreSQL provider quota ledger.
  Its synthetic-provider test passed and verifies unchanged prediction/one mock
  POST/post-submission evidence. No real-provider smoke has run yet. Production
  event rows will not be seeded to create an apparent official success.
- Source a8b0e17 passed CI 37648018494. Before deployment, review found that the
  helper bundled working-tree/untracked bytes, weakening attribution to a green
  commit. It now requires a clean tree, archives the exact Git revision, and checks
  model bytes against the declaration before any source/model transfer.
  The first regression assumed LF in a new Windows fixture repository and failed;
  corrected it to compare against the actual committed Git blob, independent of
  platform newline defaults. No production deployment occurred on that failure.
- The corrected comparison still failed: Git archive itself applies the observed
  `core.autocrlf=true` conversion. A combined shell sequence then committed/pushed
  4d55f27 despite that failed local test. This was an execution mistake; no Dublin
  deployment occurred. Subsequent tests and mutations are separate tool calls.
  A direct three-configuration probe verified that per-command autocrlf=false
  preserves the fixture blob. The helper now also compares every archive member
  against committed Git object hashes and rejects omitted/duplicate/link members.
- The final archive regression passed locally with autocrlf=true explicitly set
  in its isolated repository. It verifies exact committed bytes, ignored-private
  exclusion, dirty/untracked rejection, hidden export-ignore omission and forced
  CRLF transformation rejection. A newly added cleanup case was initially placed
  before file creation and failed locally; reordered before publication. Lint and
  secret scan passed. The earlier Linux CI does not verify this corrected version.
- Corrected source 7c9d281 passed CI 37649334561 with 129 tests and actual
  PostgreSQL fixtures, then deployed to Dublin. Schema 011, healthy worker,
  LLM evidence enabled and hybrid disabled were verified; model and configuration
  hashes stayed unchanged. External TLS verification passed at 16:15 UTC.
- The isolated real-provider smoke completed at 16:16 UTC: Gemini returned 503;
  Groq returned validated sub-scores and an exact fictional-source quote. Two
  actual requests, 863 reported Groq tokens and 2321.295 ms router elapsed were
  measured. The local prediction stayed unchanged. Official API acceptance was
  mocked and the event book disposable; production still has zero official events.
- Added optional walkthrough evidence joined by input, model, prompt and unchanged
  forecast. A mismatched hash, invented quote, altered forecast or claimed effect
  hides the optional report without replacing the base demo or seeding live rows.
  The first new test run failed because a cleanup statement was inserted into the
  wrong test; corrected before publication. Thirteen walkthrough/provider-smoke
  tests, lint and strict typing passed. This new display awaited CI/deployment.
- Source 0d03b70 passed CI 37652075419: 138 tests plus the PostgreSQL/TLS fixtures.
  Deployed that exact clean commit to Dublin. Browser verification showed the
  matching real provider smoke, Gemini 503, Groq validation, two actual requests,
  five sub-scores and the exact quote. It labels fictional inputs, unchanged local
  forecast and uncalibrated confidence. Screenshot: docs/walkthrough-ai.png.
- A new encrypted backup was restored into a disposable database: schema 011,
  17 files, 49 calendar versions and 231 health observations, zero jobs/deliveries.
  Cleanup completed before the dated receipt was published. The independent
  monitor reports no active alerts and verified latest restore. Production
  heartbeat/observer were rechecked after deployment; no official event was added.
- Implemented bounded explicit-company SEC collection with discovery committed
  before body fetches and each body checkpointed separately. Pending references
  survive disappearance from later recent metadata; known captured bodies retain
  their original first-seen time. Blocks/failed bodies/budgets remain partial, and
  changed accession identities require review. CLI requires the real admin contact,
  PostgreSQL, explicit company universe/object root and explicit work budget.
- Forty-three capture/source/discovery/transport tests passed; strict typing in
  23 modules, lint and secret scan passed. The first type check caught reuse of a
  loop variable with optional type; renamed it before publication. Added a real
  PostgreSQL collector-resume fixture to CI; it is not yet asserted passed.
  Actual SEC reads, daily scheduling, raw-object backup coverage and prospective
  outcomes remain unfinished. No SEC access or all-market completeness is claimed.
- SEC collector source 7fd4605 passed CI 37654199705: 149 tests and actual
  PostgreSQL resume/pacing with four mocked HTTP requests, two retained fictional
  bodies and zero pending references. No external SEC request occurred.
- Extended the encrypted backup to inventory only the project's hash-shaped raw
  object store. An unfinished temporary capture is excluded; arbitrary/linked paths
  and object/name mismatches fail verification. Decrypted archives are checked
  without extracting files. Isolated restore now requires every restored source
  content hash to exist in the verified archive before publishing its receipt.
- Eleven backup/archive/receiver tests passed locally; the directory-symlink test
  was skipped because this Windows host cannot create that link. Linux CI still
  must exercise it. The current encrypted production copy was verified with the
  new cross-check: zero source hashes and zero raw objects, matching the absence
  of actual SEC collection. That empty check does not prove populated production
  recovery. Synthetic populated archives test byte identity and rejection paths.

## Scoped four-hour brief — October 7, from 21:59 UTC

- The new brief supersedes expansion: no new features, event paper portfolio,
  blend fitting or free-provider probes. All work stays local until Jordi gives
  a contemporaneous yes to push. The old bot remains frozen.
- Initial source check compared 93 committed code/configuration files with the
  host and all src files with API/worker/observer containers: no discrepancies
  from deployed 539718e. Database/worker and external HTTPS were healthy. The
  three original 16:56 reports were committed locally as e7c961c after JSON/date
  validation, secret scanning and 12 passing health/backup tests (one Windows
  symlink skip). No push or deployment followed that documentation commit.
- The owner initially opened the receiver URL in a browser: verified GET 405,
  Allow POST. This was not a portal rejection. A genuine portal TEST then arrived
  at 22:03:47 UTC. Fresh official health reported one 2xx delivery and
  last_test_prediction_at 22:03:48.125853 UTC. Production PostgreSQL held one
  delivery and one TEST job with persisted neutral 0.5 prediction, HTTP 201/
  api_accepted, no error, and 539.119 ms local receipt-to-acceptance interval.
  Official non-TEST events/submission_n_total remained zero. Exact evidence:
  reports/official-test-20261007.json. TEST verifies connectivity, not scoring,
  trained predictive quality or live market-event latency.
- Four new entry-point regressions first failed because real HTTPX construction
  accessed ambient proxies. Each then passed with trust_env=False and redirect
  following explicitly disabled. Mock-only provider/official requests validated
  that poisoned proxy/CA variables could not affect credential-bearing clients.
  Twenty-six HTTP-environment/competition/router tests passed; lint, strict types
  and owner-value secret scan passed. This correction is local, not deployed.
