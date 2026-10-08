# Scoring readiness — 12 October 2026

Codex checklist authored from read-only production checks on 7 October,
22:49–22:53 UTC (8 October in Madrid). Evidence:
[operational/backup audit](../reports/scoring-readiness-readonly-20261008.json),
[external HTTPS 443](../reports/https443-20261008.json),
[exact deployed source and CI](../reports/deployment-cee53c0-20261007.json).
No code, model, service, wallet, provider quota or competition setting changed
for this checklist. No new restore or backup was launched.

**Later incident supersedes the initial no-alert snapshot:** the retained official
observation at 7 October 23:44:03 UTC reports 15 consecutive webhook 4xx failures.
Public health and the walkthrough still respond, but this does not establish
signed delivery readiness. The original TEST is still the only accepted event;
the exact rejection cause remains unknown. The prepared redacted logger is local
and not deployed. [Follow-up evidence](../reports/delivery-failures-followup-readonly-20261008.json),
[incident and remaining gates](INCIDENT-2026-10-08-delivery-4xx.md).

**Nightly follow-up:** the scheduled 8 October 04:10 UTC backup completed with
service exit 0. Its exact encrypted bytes/SHA match on Dublin and the scoped
Frankfurt backup directory. The older restore receipt applies to a different
archive; restoration of this new backup is not verified. The read-only observation
still reports the delivery-failure alert and no non-TEST accepted events.
[Nightly evidence](../reports/nightly-backup-readonly-20261008.json).

**Proxy follow-up:** the local real HAProxy/Caddy comparison now preserves the
same signed body/header bytes on both paths and one durable SQLite receipt.
This does not verify the cloud ingress or replace Jordi's signed portal TEST.
[Actual fixture](../reports/two-proxy-bytes-20261008.json).

## Initial readiness snapshot and unresolved gates

| Gate | Verified observation | Remaining limit |
| --- | --- | --- |
| Source | Deployed cee53c0 matched host and running containers; CI 37696439274 passed 174 tests | New documentation is local, not a new deployment |
| Genuine official TEST | One signed portal TEST accepted at 22:03 UTC; neutral 0.5 persisted; official HTTP 201 | Used TLS port 80; no score or trained inference |
| Standard HTTPS 443 | Owner-approved cloud rule saved; external CA/hostname valid, page/health 200, unsigned webhook 401 | Portal migration and signed TEST through 443 pending owner action |
| Host monitor | Timer enabled/active/waiting; last service exit 0; no current alerts at snapshot | Minute cadence is an existing operational choice, not an uptime guarantee |
| Alerts | Journal contains actual alert transitions and local-only notification status | No Telegram credentials; no off-host alert delivery verified |
| Nightly backup | Timer enabled/active, next trigger 8 Oct 04:10 UTC (06:10 Madrid) | Next nightly run has not happened; schedule alone does not prove success |
| Latest encrypted copy | Matching filename, 10,836,145 bytes and SHA-256 in Dublin and Frankfurt | Capture was before the genuine TEST and current deployment |
| Restore | Existing matching isolated restore receipt proves schema 011_sec_http_gate and 17 archive files | Receipt was verified at 16:56 UTC; no second restore performed |
| Competition scoring | Non-TEST received events 0, official submissions 0, no score | Future outcomes and final eligible coverage remain unverified |

The calendar is a changing schedule, not delivered events. The later read-only
calendar GET contained 3,019 scheduled records, not 3,019 received broadcasts.
The first TEST must never be included in scored-event coverage.

## Monitor and alerts: what is actually running

`eventdesk-monitor.timer` runs the independent host monitor once a minute.
The initial inspected invocation succeeded, `ExecMainStatus=0`, and its state had
`active_alerts=[]`; the later nightly follow-up has `official_delivery_or_submission_failures`. The installed monitor bytes match `ops/monitor.py` in deployed
cee53c0. It reads health, scoreboard and competition observations, not order APIs.

The health/backup alerts implemented in that source are:

- `origin_unreachable`, `worker_heartbeat_unverified`,
  `submission_deadline_at_risk`, `expired_or_rejected_predictions`;
- `https_path_unverified`, `backup_transfer_unverified`,
  `backup_age_outside_guard`, `backup_timestamp_invalid`.

Official observation alerts are `official_observations_unverified`,
`official_observations_stale`, `official_observation_failed` and
`official_delivery_or_submission_failures`.

Existing guards: a 26-hour backup-age allowance, a 20-minute official-observation
age allowance and a three-second probe budget. These are documented operational
guesses in the deployed code, not calibrated reliability or market-latency claims.
The monitor records a daily operational summary and logs alert transitions.
Telegram token/chat and Langfuse keys are absent; notifications remain local.
No new accounts, messages or optional integrations were created for this audit.

**HTTPS limitation:** the installed monitor still uses explicit TLS `:80` and its
matching dated external proof. It does not continually measure external 443.
A successful self-request does not prove the cloud inbound rule. Separate external
443 evidence exists; neither one dated probe nor no current alerts proves uptime.

Read-only inspection on Dublin:

```sh
sudo systemctl show eventdesk-monitor.timer eventdesk-backup.timer \
  --property=ActiveState,SubState,UnitFileState,LastTriggerUSec,NextElapseUSecRealtime
sudo systemctl show eventdesk-monitor.service eventdesk-backup.service \
  --property=Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
sudo journalctl -u eventdesk-monitor.service --since "24 hours ago" --no-pager
sudo cat /var/lib/eventdesk/monitor/state.json
```

Treat logs as private diagnostics; redact credentials and source materials before
sharing. Do not restart a healthy service just because a oneshot service is inactive:
the timer stays active and the service's last result is the relevant observation.

## Initial backup snapshot: rechecked bytes, existing restore only

At the initial inspection, the latest receipt pointed to `eventdesk-20261007T165611Z.tar.gz.age`.
Fresh reads verified both encrypted files, including their actual bytes and SHA:
`18bb82e983a660f8c929cc24bd15dbf1c6f0ca5262bc8ae05c308a6b12af00ad`.

The independent restore receipt matches filename, ciphertext SHA and model SHA.
It reports 17 verified archive files and an isolated PostgreSQL restore with
schema `011_sec_http_gate`; production was not overwritten. Model SHA remains
`da212d24d1f3bb2c0d8528d62160667f7ca61029e748ca8dac6b5df9a2210bce`.
The latest transfer receipt's own `restore_verified=false` is not a failure:
restoration proof is retained separately in `restore-verification.json` and matches.

This archive was captured at 16:56 UTC, before the 22:03 TEST. Its restored jobs and
deliveries were zero; it does not contain the later TEST or certify newer code.
For each subsequent nightly execution, require service exit 0 and a new latest receipt,
then compare that exact file on both hosts. A previous matching restore cannot
certify a later archive. Do not run `ops/verify_backup.py` under this read-only
brief: it creates/restores/drops a disposable database and writes proof files.
No backup retention or host configuration was changed here.

## Daily check before and during scoring

1. Confirm public HTTPS with normal certificate/hostname validation. Check
   `/healthz`: database reachable, worker recent heartbeat, fixture mode false;
   inspect retained model/config hashes and hybrid disabled.
2. Check the observer's most recent `observed_at` and collector state. Retain UTC
   timestamp, non-TEST received/accepted counts and official rolling error counters.
   Rolling counters, API acceptance and calendar schedules are separate evidence;
   do not turn them into an invented eligibility percentage or score.
3. Read the timer/service result and latest backup receipt. Compare the current
   ciphertext file and SHA on both hosts. Check age against the existing guard and
   whether restoration proof applies to this exact file. Record failures honestly.
4. Read new journal alert transitions. Without configured off-host notifications,
   a human must inspect them; no remote alert delivery has been verified.
5. For any real event, inspect retained event identity, receipt/prediction timestamps,
   deadline, inputs hash, model/config hash, submission state and official result.
   Material fallback or late/expired work must remain visible, not rewritten.
6. Keep blend and paper portfolio disabled. Do not probe LLM providers, manufacture
   events or spend quota to fill an idle calendar. Scores/outcomes must actually occur.

## Malformed delivery and uncertain acceptance

The receiver code `src/eventdesk/api.py` enforces these existing outcomes:

| Condition | Response and handling |
| --- | --- |
| Signature or verifier decoding fails | HTTP 401; no accepted inbox entry |
| Invalid event schema, non-finite JSON, body/header identity mismatch, non-TEST without cutoff | HTTP 400 before durable acceptance |
| Same delivery identity with changed bytes | HTTP 409 conflict; never replace the retained event |
| Body exceeds metadata ceiling | HTTP 413 |
| Body timeout or uncertain database acceptance | HTTP 503; a late database commit may have happened |
| Identical retry after a durable commit | Deduplicated by retained delivery identity/body; no forced second prediction |

Operational response: retain the HTTP status and UTC time, inspect private API logs
and retained event records read-only, and compare official delivery-error counters.
Do not weaken signature/schema validation, hand-edit the inbox, fabricate a signed
retry or manually send a second prediction. A 503 is not proof of rollback: inspect
durable state before concluding nothing happened. Escalate recurring failures with
redacted evidence. These statuses are infrastructure outcomes, not scores.

## Source ownership

A pre-existing untracked draft of this filename was not authored by Codex. Its
original bytes were preserved in the ignored private folder and their SHA is
recorded in the read-only audit. This replacement was written afresh from the
verified observations and deployed source. No foreign draft or Stockline change
is included in the proposed local commit. Review the staged diff before committing.
