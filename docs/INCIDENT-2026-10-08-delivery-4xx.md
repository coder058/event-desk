# Delivery 4xx incident — 8 October 2026 (Madrid)

## Verified incident

The official read-only health API and retained observer reported three consecutive
client-error deliveries, latest `2026-10-07T23:02:19.406911Z`. The original TEST
remained the only accepted job; its official prediction timestamp is
`2026-10-07T22:03:48.125853Z`. Zero non-TEST submissions and no score were observed.
[Incident snapshot](../reports/delivery-failures-readonly-20261008.json).

The monitor raised `official_delivery_or_submission_failures`. Public health GETs
on TLS 80 and standard 443 returned 200 with a reachable database and recent worker
heartbeat. This does not establish successful signed POST delivery. The runtime API
credentials matched the existing local credentials by hash; no values were exported.
API access logging was intentionally disabled, so no historical rejection body,
headers or exact HTTP status was recovered. Root cause remains unknown.

## Later read-only observation

At `2026-10-07T23:52:44Z`, public HTTPS GETs returned 200 for the dashboard,
walkthrough, health and public read-only APIs. The retained official observer
snapshot from `2026-10-07T23:44:03.534902Z` reported **15** 4xx deliveries and
**15** consecutive failures, latest delivery `2026-10-07T23:28:59.043690Z`.
It still reported one 2xx and the original TEST prediction timestamp; production
health retained one TEST/api_accepted job and the scoreboard had zero non-TEST
received/accepted events. [Follow-up evidence](../reports/delivery-failures-followup-readonly-20261008.json).

This was not a fresh authenticated portal GET. The growing count does not identify
who triggered the deliveries or whether they were TEST, non-TEST or retries.
Neither successful public GETs nor the available synthetic walkthrough diagnoses
the rejection. No URL, secret, signature gate, runtime code or production log
configuration was changed. The exact rejection cause remains unknown.

## Hypotheses, in requested order

| Hypothesis | Observation | Conclusion |
| --- | --- | --- |
| Portal currently switched to 443 | Existing portal Overview showed `https://52.17.192.36.sslip.io:80/competition/webhook` during the investigation | Current switch to 443 is not supported; exact historical URL for each failed delivery is not retained |
| Proxy changed signed bytes or headers | Production HAProxy is TCP passthrough to Caddy; both origin health routes work. Earlier Linux CI exercised signed TLS 80; the genuine earlier TEST also passed that route | Config and GETs do not prove byte/header equivalence for failed requests or the direct 443 route; not ruled out |
| Proxy transport changes the tested signed bytes | ASGI control passed first. Later, an isolated WSL fixture used copied/hash-matched deployed HAProxy/Caddy executables and cee53c0 receiver source. Both real proxy paths preserved the full body and three signing-header values; two 200 ACKs retained one delivery/job, and altered bytes produced 401 on both | The local real-proxy comparison passed. Cloud ingress and actual failed portal payloads remain untested; this does not identify the historical cause |
| Gross current host clock drift | `NTPSynchronized=yes`, Chrony active/running, leap status Normal at `2026-10-07T23:24:17Z` | Current gross NTP drift is not supported; failed delivery timestamp/portal clock remain unavailable |
| Signature timestamp is outside tolerance | Vendored official verifier uses 5 × 60 seconds; receiver does not override it | Expired, missing or malformed signing timestamps remain possible; actual failed headers were not retained |
| A non-TEST/new-schema/conflicting delivery was rejected | Read-only database at `23:25:16Z`: one delivery, one TEST/api_accepted job; no dedicated rejections table or incoming-status column | Accepted-event table cannot identify rejected event types; schema/conflict hypothesis remains unknown |

Chrony reported system time **0.000003954 seconds slow** of NTP, last offset
**-0.000007538 seconds** and RMS offset **0.000005467 seconds**. These are actual
current Chrony estimates, not independently measured portal-to-host offsets or a
historical guarantee. `timedatectl timesync-status` could not query timesyncd;
Chrony is the active synchronizer, so that alone was not a clock failure.

Read-only clock reproduction:

```sh
timedatectl show --property=NTPSynchronized --property=TimeUSec --property=Timezone
chronyc tracking
systemctl show chrony.service --property=ActiveState --property=SubState
```

The receiver explicitly uses 400 for schema, identity and cutoff rejection; 401
for verifier failure; 404 for unconfigured slots; 409 for changed bytes under the
same accepted delivery; and 413 for size. There is no explicit incoming 422 branch
in this receiver. An official aggregate `http_4xx` does not identify one of these
statuses or establish that this app, rather than another HTTP layer, generated it.
Job submission responses describe outbound predictions, not inbound rejections.

## Actual local proxy comparison completed; public portal path still pending

The attempted local fixture startup failed because `docker` is unavailable in this
Windows shell. No Docker engine was installed and no production fixture/container
was started to work around that restriction. [Clean-checkout attempt](REPRODUCE.md).
The existing `compose.mux.fixture.yaml` publishes the TLS-80 mux path only; its
signed smoke does not compare a directly published fixture Caddy-443 route.

The later native WSL run avoided installing a Docker engine. It copied only the
public deployed executables/libraries by read-only SSH, verified their hashes and
ran them with private loopback ports/CA/storage. The exact cee53c0 receiver source
was archived locally; all 28 source files and installed runtime API package files
matched that Git revision. HAProxy 3.2.25 and Caddy 2.11.7 processed the same signed
Unicode/whitespace request via TCP passthrough and direct TLS termination.

Both paths retained the exact body and signing-header bytes and returned 200;
one delivery/job remained in disposable SQLite. Altering the body under the same
signature returned 401 through each path. CA/hostname validation stayed enabled,
Caddy did not install its CA globally, and all owned fixture listeners were released.
The first private helper had a final row-count API error; the corrected helper and
repository runner passed. No VPS service, secret, firewall or runtime code changed.
[Actual proxy evidence](../reports/two-proxy-bytes-20261008.json),
[reproduction and exact scope](TWO-PROXY-REPRODUCE.md).

This establishes the local proxy comparison, not the failed public requests.
Local DNS, CA, ports, SQLite and Python 3.14 differ from production; the latter
Dockerfile uses Python 3.12. Actual portal payloads/timestamps remain unavailable,
PostgreSQL concurrency was not exercised here and no official POST was made.
The incident cause and a genuine signed portal TEST through standard 443 remain
unverified. The original whole Docker/Compose startup gate also remains unrun.

## Prepared minimal change: private rejection reasons

Because read-only evidence cannot identify the past cause, a local proposal adds
one log per known receiver rejection:

```text
webhook_rejection status=401 reason=signature_timestamp_outside_tolerance
```

Only HTTP code and a fixed enumerated reason are logged. No body, signing header,
secret, request URL, delivery/event identity or exception text is included. Existing
HTTP codes and client-facing messages are preserved. Signature, size, deadline,
conflict and durable-acceptance gates remain in place. No rejection table, public
endpoint, scoring behavior, credential or provider quota is added or changed.

The signature sub-reasons use fixed messages from the vendored official verifier;
unknown verifier messages fall back to a generic reason without exporting the
message. If those trusted messages change, the classification may become less
specific; verification and rejection still happen.

Initial tests first: **9 failed** because the expected diagnostic log was absent,
while existing HTTP statuses already matched. After the proposal, **13 diagnostic
cases passed**: signature presence/age/format, changed bytes, invalid schema,
identity/cutoff, unknown slot, conflict, oversize, DB/budget uncertainty and the
ASGI-only two-origin control. Body/header sentinels and public fixture signatures
are checked for absence from rejection logs. Ruff and strict mypy pass. The full suite passed **186 tests, one skipped**
in **170.60 seconds**; the Windows symlink test is the skipped case.

This proposal has not been pushed or deployed. It cannot reconstruct past failures.
Jordi must approve publication/deployment before production can expose a future
rejection reason in private logs. The owner question about the attempted TEST and
its displayed error remains pending; no synthetic signed production POST was sent.
