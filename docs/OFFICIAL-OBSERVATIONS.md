# Official observations, not inferred score coverage

The `official-observer` production container reads `GET /events` and `GET /health`
using each configured submission's existing key. It cannot trigger a webhook or
submit a prediction. It is separate from deadline-critical workers. Fixture compose
does not run it or require keys.

The ten-minute cadence, fifteen-second total read guard and sixteen-MiB response
cap are uncalibrated operational choices. A failed attempt leaves the last complete
snapshot intact and records a separate failure pulse. Host alerts distinguish
failed attempts, stale observations and reported delivery/submission failures.

Schema 008 stores normalized calendars once per content hash and appends health
observations with both original-response hashes and request-start/completion times.
The two GET requests are sequential, not an atomic broker/competition snapshot.
Unknown fields, submission IDs and arbitrary status strings are not exported.
Calendar corrections create a new version; earlier observations stay unchanged.

`/api/competition` exposes aggregates and the official rolling 24-hour counters.
Calendar capacity days use America/Chicago as a display convention, following the
announced registration timezone. This is not proof of the organizers' event-date
eligibility convention; both the grouping and that uncertainty are explicit.
Entries due within the scoring window are **scheduled**, not confirmed broadcasts.
The API calendar can be partial or revised, and organizers choose the final eligible
scored set. No denominator or percentage of official eligible coverage is invented.
The local prediction ledger is cumulative and therefore is not compared directly
with official rolling counters as if both covered the same interval.

Primary schema: [official API client](https://github.com/explaining-markets/examples/blob/main/src/examples/client.py)
and [response models](https://github.com/explaining-markets/examples/blob/main/src/examples/schemas.py).
Eligibility remains governed by the [binding rules](https://explainingmarkets.ai/contest-rules).
