# External actions and unresolved dependencies

## Owner action — connect the existing submission and send the portal test

External HTTPS was verified on October 7 at 11:25 UTC using the already reachable
TCP 80 listener. Paste `https://52.17.192.36.sslip.io:80/competition/webhook` into
the Webhook URL field of the existing LLMSITO submission, click Save webhook URL,
then Send test event. No new account or paid provider is required. Do not replace
credentials or paste them in chat. The portal currently shows Setup 1/3 and an
empty URL; actual portal delivery/prediction remain unverified.

The nonstandard port is explicit and uses verified TLS, not plaintext HTTP.
Standard HTTPS 443 still times out; the signed-out AWS session is no longer a
dependency for this tested route. Acceptance of this URL by the portal is still
an external check. No certificate-warning bypass or firewall weakening was used.

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

- Official portal delivery and prediction after the owner saves the verified URL.
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
