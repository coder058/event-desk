"""Verified fixture TLS -> transparent TCP -> Caddy -> signed durable receipt, no owner keys."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import ssl
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

# SOURCE: official public signing test vector, not an owner credential.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"
# SOURCE: loopback port declared in the isolated Compose overlay.
ORIGIN = "https://localhost:18881"


def main() -> None:
    # Run inside the fixture Compose project to guarantee this certificate is from that Caddy only.
    compose = ["docker", "compose", "-f", "compose.yaml", "-f", "compose.mux.fixture.yaml"]
    with tempfile.TemporaryDirectory(prefix="fixture-tls-") as directory:
        certificate = Path(directory)/"root.crt"
        # GUESS: bounded cold-start readiness window; not an ACK or latency calibration. # UNCALIBRATED GUESS
        deadline = time.monotonic()+60
        while time.monotonic() < deadline:
            fetched = subprocess.run(compose+["exec", "-T", "caddy", "cat",
                "/data/caddy/pki/authorities/local/root.crt"], capture_output=True)
            if fetched.returncode == 0:
                certificate.write_bytes(fetched.stdout)  # Public CA certificate; no private key is read.
                break
            time.sleep(1)
        else:
            raise RuntimeError("Fixture Caddy public CA not available")
        context = ssl.create_default_context(cafile=str(certificate))
        with httpx.Client(verify=context, trust_env=False, timeout=5) as http:
            while time.monotonic() < deadline:
                try:
                    health = http.get(ORIGIN+"/healthz")
                    if health.is_success:
                        assert health.json()["fixture_mode"] is True
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            else:
                raise RuntimeError("Fixture TLS receiver did not become healthy")
            delivery = "fixture-mux-"+str(time.time_ns())
            # PLACEHOLDER: synthetic event, unicode and whitespace exercise exact HMAC byte preservation.
            body = json.dumps({"id": delivery, "event_id": delivery, "event_type": "EARNINGS_RELEASE",
                "knowledge_cutoff": "2026-01-01T00:00:00Z", "metadata": "naïve — 🚀",
                "focal_assets": [{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}]},
                ensure_ascii=False, indent=2).encode("utf-8")
            timestamp = str(int(time.time()))
            signature = base64.b64encode(hmac.new(base64.urlsafe_b64decode(SECRET.removeprefix("whsec_")),
                delivery.encode()+b"."+timestamp.encode()+b"."+body, hashlib.sha256).digest()).decode()
            headers = {"Webhook-Id": delivery, "Webhook-Timestamp": timestamp,
                "Webhook-Signature": "v1,"+signature}
            started = time.perf_counter()
            response = http.post(ORIGIN+"/competition/webhook", content=body, headers=headers)
            assert response.status_code == 200
            ack_ms = (time.perf_counter()-started)*1000  # SOURCE: seconds -> milliseconds.
            assert http.post(ORIGIN+"/competition/webhook", content=body, headers=headers).status_code == 200
            assert http.post(ORIGIN+"/competition/webhook", content=body+b" ", headers=headers).status_code == 401
            redirect = http.get("http://localhost:18881/healthz", follow_redirects=False)
            assert redirect.status_code == 308 and redirect.headers["location"] == ORIGIN+"/healthz"
            # GUESS: fixture worker observation allowance, not a production promise. # UNCALIBRATED GUESS
            deadline = time.monotonic()+30
            while time.monotonic() < deadline:
                retained = http.get(ORIGIN+"/api/events/"+delivery)
                if retained.is_success and retained.json()["state"] == "simulated":
                    break
                time.sleep(1)
            else:
                raise RuntimeError("Signed TLS fixture was not processed")
            print(json.dumps({"fixture_tls_verified": True, "ack_ms": ack_ms,
                "duplicate_ack": True, "changed_bytes_rejected": True, "plaintext_redirect": True,
                "worker_state": "simulated", "limits": "One synthetic event; no public/official coverage or live latency proof"}))


if __name__ == "__main__":
    main()
