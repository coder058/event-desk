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
- Reproduction of the supplied archive results; do not quote them as our findings yet.
- Free-tier model availability and account-specific quota limits.
- Ten scoring days are future observations, not an engineering shortcut.
