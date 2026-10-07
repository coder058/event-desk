# External actions and unresolved dependencies

## Resolved — genuine portal TEST

October 7, 22:03 UTC: the configured TLS 80 webhook received one genuine portal
TEST. Fresh official health reported a 2xx delivery and the accepted TEST prediction
timestamp; PostgreSQL retained one delivery, the neutral 0.5 payload and HTTP 201/
api_accepted. [Exact evidence](reports/official-test-20261007.json).
Non-TEST events and official submission_n_total were still zero. TEST is not scored.
Opening this POST-only webhook in a browser returns expected GET 405, not a portal
rejection. No synthetic event was inserted to manufacture a success.

## Resolved — standard HTTPS 443; portal migration pending

At October 7, 22:45 UTC the owner-confirmed HTTPS/TCP/443 IPv4 rule was saved
in Lightsail Dublin. External CA/hostname validation, dashboard/health 200 and
unsigned webhook 401 passed. [Evidence](reports/https443-20261008.json).

The owner must save `https://52.17.192.36.sslip.io/competition/webhook` in the
existing competition portal and press Send test event to verify official delivery
through 443. The prior accepted official TEST used the working TLS 80 URL.
Opening the webhook URL as a browser GET correctly returns 405.

## Publication frozen by the latest instruction

Five approved commits through cee53c0 were pushed and deployed before the latest
freeze. Exact CI 37696439274 passed 174 Linux tests, Compose fixtures and TLS mux.
Post-deploy host/container byte comparisons matched that source. New reports and
documentation remain local. No further push, deployment or spending is authorized.

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
