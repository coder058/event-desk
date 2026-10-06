# External actions and unresolved dependencies

## Owner action — HTTPS networking

Dublin origin and PostgreSQL are running, and Caddy obtained a valid certificate.
Public HTTP 80 responds; public HTTPS 443 times out. The host firewall accepts traffic.
The existing Lightsail session is signed out. Log in on the opened AWS tab and leave
the Dublin instance networking page available so the HTTPS rule can be verified.
No password, MFA code or AWS key should be shared in chat. This is an additional
external dependency discovered during the actual deployment, not a new account.

## Owner action — portal test, after HTTPS is reachable

Once HTTPS is verified, paste `https://52.17.192.36.sslip.io/competition/webhook` in the
existing competition submission portal and click Send test event. No new account
or paid provider is required. Do not paste credentials in chat.

## Optional integrations

Telegram and Langfuse variables are empty. Local alerts/traces will be used.
These do not block Phase A.

## Verification still to perform

- Public inbound HTTPS on Dublin (certificate issuance succeeded).
- Archive baseline reproduction completed; measured results are in reports/archive-eval.md.
- Gemini is intermittently unavailable (503); Groq has returned 429 even when
  its minute-token header showed capacity. Numeric quota diagnostics are retained;
  account-wide usage and additional limits can differ from this project's counters.
  On October 6 Gemini returned a daily-request 429 and a 77,956-second RetryInfo;
  the collector respects that cooldown. This is not a reason to interrupt the
  always-on local model, or evidence of capacity for another Gemini model.
- Hybrid calibration remains insufficient: collect current-prompt Q2/Q3 samples
  under those limits, then evaluate the fitted mapping before approving deployment.
- Full trained-model HTTP/PostgreSQL fixture replay passed at source 2e8792f:
  400 durable ACKs and 400 simulated results in 10.626 seconds; maximum ACK
  1.249 seconds. This is
  isolated infrastructure evidence, not official competition coverage. Initial
  startup/load attempts failed and remain recorded in PROGRESS.md.
- Ten scoring days are future observations, not an engineering shortcut.
