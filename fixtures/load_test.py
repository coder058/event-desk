"""Full HTTP/PostgreSQL/model fixture load. Refuses any production receiver."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import hmac
import json
import statistics
import time
from pathlib import Path

import httpx

# SOURCE: official public signing vector; not an owner secret.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"
# SOURCE: mission requests a 400-event busy-day dry run.
EVENTS = 400
# GUESS: bounded HTTP concurrency to exercise simultaneous receipt, not claimed production capacity.
CONCURRENCY = 16


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/tmp/eventdesk-fixture-load.json"))
    parser.add_argument("--origin", default="http://127.0.0.1:8000")
    parser.add_argument("--material-file", type=Path)
    args = parser.parse_args()
    async with httpx.AsyncClient(timeout=20) as client:
        before = (await client.get(args.origin + "/healthz")).json()
        if before.get("fixture_mode") is not True:
            raise RuntimeError("Refusing load test against production")
        replay_materials = json.loads(args.material_file.read_text()) if args.material_file else None
        if replay_materials is not None and (not isinstance(replay_materials, list) or len(replay_materials) != EVENTS):
            raise ValueError("Archived fixture must contain exactly the mission's event count")
        baseline = before["states"].get("simulated", 0)
        semaphore = asyncio.Semaphore(CONCURRENCY)
        prefix = "load-" + str(time.time_ns())
        key = base64.urlsafe_b64decode(SECRET.removeprefix("whsec_"))
        ack_ms = []
        started = time.perf_counter()
        async def send(index: int) -> None:
            async with semaphore:
                delivery_id = prefix + "-" + str(index)
                materials = replay_materials[index] if replay_materials is not None else {
                    "items": [{"id": "earnings-call-facts", "content": [
                        "Revenue increased this quarter and management maintained full-year guidance.",
                        "Operating costs declined, while the company reported uncertainty in customer demand."]}]}
                raw = json.dumps({"id": delivery_id, "event_id": delivery_id,
                    "event_type": "EARNINGS_RELEASE", "knowledge_cutoff": "2026-01-01T00:00:00Z",
                    "focal_assets": [{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}],
                    "fixture_materials": materials}).encode()
                timestamp = str(int(time.time()))
                signature = base64.b64encode(hmac.new(key, delivery_id.encode() + b"." + timestamp.encode() + b"." + raw,
                                                      hashlib.sha256).digest()).decode()
                sent = time.perf_counter()
                response = await client.post(args.origin + "/competition/webhook", content=raw,
                    headers={"Webhook-Id": delivery_id, "Webhook-Timestamp": timestamp,
                             "Webhook-Signature": "v1," + signature})
                if response.status_code != 200:
                    # GUESS: bounded fixture-only diagnostic; this script refuses production beforehand.
                    raise RuntimeError(f"Fixture ACK failed: HTTP {response.status_code}; {response.text[:200]}")
                ack_ms.append((time.perf_counter() - sent) * 1000)
        await asyncio.gather(*(send(index) for index in range(EVENTS)))
        while time.perf_counter() - started < 300:  # SOURCE: official five-minute submission budget.
            health = (await client.get(args.origin + "/healthz")).json()
            if health["states"].get("simulated", 0) - baseline == EVENTS:
                break
            await asyncio.sleep(.25)  # GUESS: local fixture completion polling.
        else:
            raise RuntimeError("Fixture events did not finish within the official time budget")
        elapsed = time.perf_counter() - started
        percentiles = statistics.quantiles(ack_ms, n=100, method="inclusive")
        report = {"kind": "http_postgres_fixture_simulation", "events": EVENTS,
                  "ack_count": len(ack_ms), "completed_simulated": EVENTS,
                  "seconds": elapsed, "ack_p50_ms": statistics.median(ack_ms),
                  "ack_p95_ms": percentiles[94], "ack_p99_ms": percentiles[98],
                  "ack_max_ms": max(ack_ms), "concurrency": CONCURRENCY,
                  "fixture_input_kind": "archived_official_disclosures" if replay_materials is not None else "synthetic",
                  "worker_model_sha256": health.get("worker", {}).get("details", {}).get("model_hash"),
                  "limits": "Synthetic text/targets and simulated submission, not competition coverage or model accuracy"}
        if replay_materials is not None:
            report["limits"] = "Archived official inputs and simulated fixture submission; no outcomes, official coverage or model accuracy measured"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())
