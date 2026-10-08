# External actions and unresolved dependencies

## Resolved — genuine portal TEST and standard HTTPS configuration

Two genuine portal TESTs are now accepted. The latest was received on 8 October
at 13:13:57 Madrid; fresh official health and read-only PostgreSQL queries agree:
2xx delivery, neutral prediction persisted, HTTP 201/api_accepted and one delivery/
job for that event. Consecutive failures are zero. TEST does not score.
[Latest evidence](reports/official-test-20261008.json).

A manual browser review confirmed the portal's saved webhook is
`https://52.17.192.36.sslip.io/competition/webhook` and the submission is Live.
The Health tab shows two 2xx, fifteen older 4xx and zero consecutive failures.
No further owner TEST is required for this verification. The receiver does not
retain the ingress port per request; the saved URL was independently inspected.

## Resolved — diagnostic publication and authority for this web repair

Jordi approved publication/deployment with “ok hazlo”. Source 8553954 passed CI
37768023493 (187 Linux tests and Docker fixtures), was deployed and matched
installed bytes. The private rejection logger was verified with an unsigned
401 probe. [Evidence](reports/deployment-8553954-20261008.json).

The latest instruction asks Codex to inspect and correct the website directly,
with permission, rather than return routine work to the owner. The current
presentation and reproduced webhook-compatibility repairs will be tested, published and deployed within that scope.
This does not authorise new functions, a paper portfolio, blend or spending.

The historical 15 rejections still cannot be reconstructed. A new rejected
request can now expose a private enumerated reason. The review reproduced an
incompatible required webhook-cutoff field against the official example; its
scoped repair is recorded in the incident report. A genuine non-TEST round trip
remains to be observed. Do not manufacture an event or infer the historical cause.

## Repository clarification resolved

Jordi confirmed Event Desk is the only repository and INBOX_CODEX.md the only
inbox. Stockline belongs to Cursor; no Stockline file or test was modified/run.
The foreign untracked scoring draft was preserved privately with its SHA and
replaced by a Codex-authored checklist from fresh read-only operational evidence.

## Optional integrations

Telegram and Langfuse variables are empty. Local alerts/traces will be used.
These do not block Phase A.

## SEC ingestion identity, before external EDGAR collection

No SEC_USER_AGENT is configured. The public Git author address is a noreply
address, not a verified admin contact. Before automated SEC reads, add
`SEC_USER_AGENT="EventDesk Research your-existing-admin-email"` to the existing
root-owned `/etc/eventdesk/env`, using an actual contact address. This needs no
new account or API key; do not paste the address/credentials into this chat.
The contact will be sent in the User-Agent header to SEC, as its fair-access
guidance requests. It is not published on our page or in Git. Parser/storage work
can continue without claiming live EDGAR ingestion; Phase A is independent.

## Verification still to perform

- Official scored observations and coverage after the scoring window actually starts.
- Archive baseline reproduction completed; measured results are in reports/archive-eval.md.
- Gemini is intermittently unavailable (503); Groq has returned 429 even when
  its minute-token header showed capacity. Numeric quota diagnostics are retained;
  account-wide usage and additional limits can differ from this project's counters.
  On October 6 Gemini returned a daily-request 429 and a 77,956-second RetryInfo;
  the collector respects that cooldown. This is not a reason to interrupt the
  always-on local model, or evidence of capacity for another Gemini model.
- The first fixed hybrid was evaluated on 42 Q2 and 28 Q3 valid AI events. It
  underperformed local-only on both the full imputed view and paired scorer cohort.
  It remains unapproved; more label-blind evidence is needed, not a guessed blend.
- Full trained-model HTTP/PostgreSQL fixture replay passed at source 2e8792f:
  400 durable ACKs and 400 simulated results in 10.626 seconds; maximum ACK
  1.249 seconds. This is
  isolated infrastructure evidence, not official competition coverage. Initial
  startup/load attempts failed and remain recorded in PROGRESS.md.
- Ten scoring days are future observations, not an engineering shortcut.
