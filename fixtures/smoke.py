"""Keyless Compose E2E: wait for receiver, deliver a signed fixture, observe simulated result."""
import base64
import hashlib
import hmac
import json
import time

import httpx

# SOURCE: official signing vector; this is public synthetic test material.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"
ORIGIN = "http://127.0.0.1:8000"
for _ in range(60):  # GUESS: startup wait, not a prediction threshold.
    try:
        result = httpx.get(ORIGIN + "/healthz", timeout=2)
        if result.status_code == 200:
            assert result.json()["fixture_mode"] is True
            break
    except httpx.HTTPError:
        pass
    time.sleep(1)
else:
    raise SystemExit("Fixture receiver did not become healthy")
delivery = "fixture-" + str(time.time_ns())
body = json.dumps({"id": delivery, "event_id": delivery, "event_type": "EARNINGS_RELEASE",
                   "knowledge_cutoff": "2026-01-01T00:00:00Z",
                   "focal_assets": [{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}]}).encode()
timestamp = str(int(time.time()))
signature = base64.b64encode(hmac.new(base64.urlsafe_b64decode(SECRET.removeprefix("whsec_")),
                                     delivery.encode() + b"." + timestamp.encode() + b"." + body,
                                     hashlib.sha256).digest()).decode()
response = httpx.post(ORIGIN + "/competition/webhook", content=body,
                     headers={"Webhook-Id": delivery, "Webhook-Timestamp": timestamp,
                              "Webhook-Signature": "v1," + signature})
assert response.status_code == 200
for _ in range(30):  # GUESS: local smoke polling window.
    results = httpx.get(ORIGIN + "/api/predictions").json()
    if any(result["event_id"] == delivery and result["state"] == "simulated" for result in results):
        print("Compose signed fixture -> durable queue -> model -> simulation verified")
        break
    time.sleep(1)
else:
    raise SystemExit("Fixture processing did not complete")
