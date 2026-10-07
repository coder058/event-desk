# Standard HTTPS: owner check in Lightsail

Read-only checks on October 7 at 22:15 UTC:

- External TLS 80 passed certificate validation; external 443 timed out.
- VPS loopback 443 passed certificate validation and `/healthz` returned HTTP 200.
- The host listens on IPv4/IPv6 443; UFW is inactive and INPUT accepts traffic.
- Docker's examined chains include ACCEPT and DNAT for the Caddy 443 listener;
  DOCKER-USER is empty. No host or cloud rule was changed.
- The existing AWS browser tab could not be read (two browser-control timeouts).
  AWS CLI is unavailable locally. **The Lightsail firewall is not verified.**

These observations suggest an upstream restriction but do not prove its cause.
The working TLS 80 URL already received a genuine portal TEST and accepted reply.

## Jordi: inspect the cloud rule

1. Sign in to the [existing Lightsail console](https://lightsail.aws.amazon.com/).
2. Choose **Instances**, then the Dublin instance with public IPv4 **52.17.192.36**.
3. Open **Networking**, then **IPv4 Firewall**.
4. If the rule is missing, choose **Add rule**: **HTTPS**, **TCP**, **443**.
   If HTTPS is not offered, choose **Custom / TCP / 443**.
5. This is the public HTTPS page/webhook: allow all IPv4 sources for this specific
   port, then **Create**. Do not open the database or change SSH access.
6. Tell Codex whether the rule was absent, already present, or restricted.

[Official AWS instructions](https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-editing-firewall-rules.html).

After the owner check, verify externally with CA/hostname validation before
changing public URLs. Expected standard webhook:
`https://52.17.192.36.sslip.io/competition/webhook`.
Keep the tested `https://52.17.192.36.sslip.io:80/competition/webhook` configured
until standard HTTPS is actually verified. Do not bypass certificate warnings.
