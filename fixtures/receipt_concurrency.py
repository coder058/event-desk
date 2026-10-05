"""Real HTTP/PG identity races, permitted only inside the isolated fixture project."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import time

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eventdesk.store import Delivery, Job, Store

# SOURCE: official public signing test vector, never an owner credential.
SECRET = "whsec_dGVzdC1zZWNyZXQtMzItYnl0ZXMtZm9yLXRlc3R2ZWN0"


async def main() -> None:
    origin = "http://127.0.0.1:8000"
    store = Store(os.environ["DATABASE_URL"])
    async with httpx.AsyncClient(timeout=20) as client:  # SOURCE: official ACK maximum.
        if (await client.get(origin + "/healthz")).json().get("fixture_mode") is not True:
            raise RuntimeError("Refusing receipt races against production")
        prefix = "race-" + str(time.time_ns())

        async def send(delivery: str, event_id: str, asset: str = "FIXTURE") -> int:
            raw = json.dumps({"id": delivery, "event_id": event_id, "event_type": "TEST",
                "focal_assets": [{"identifier_type": "TICKER", "identifier_value": asset}]}).encode()
            timestamp = str(int(time.time()))
            key = base64.urlsafe_b64decode(SECRET.removeprefix("whsec_"))
            signature = base64.b64encode(hmac.new(key,
                delivery.encode() + b"." + timestamp.encode() + b"." + raw, hashlib.sha256).digest()).decode()
            return (await client.post(origin + "/competition/webhook", content=raw,
                headers={"Webhook-Id": delivery, "Webhook-Timestamp": timestamp,
                         "Webhook-Signature": "v1," + signature})).status_code

        # GUESS: twenty concurrent retransmissions exercise a race, not a capacity calibration.
        statuses = await asyncio.gather(*(send(prefix, prefix) for _ in range(20)))
        assert statuses == [200] * 20, statuses
        with Session(store.engine) as session:
            job = session.scalar(select(Job).where(Job.event_id == prefix))
            assert job is not None
            original_deadline = job.deadline
            assert session.scalar(select(func.count()).select_from(Job).where(Job.event_id == prefix)) == 1
            assert session.scalar(select(func.count()).select_from(Delivery).where(Delivery.event_id == prefix)) == 1
        statuses = await asyncio.gather(*(send(prefix + "-redelivery-" + str(i), prefix) for i in range(20)))
        assert statuses == [200] * 20, statuses
        assert await send(prefix, prefix, "CHANGED") == 409
        assert await send(prefix + "-identity-conflict", prefix, "CHANGED") == 409
        with Session(store.engine) as session:
            job = session.scalar(select(Job).where(Job.event_id == prefix))
            assert job is not None and job.deadline == original_deadline
            assert session.scalar(select(func.count()).select_from(Job).where(Job.event_id == prefix)) == 1
            assert session.scalar(select(func.count()).select_from(Delivery).where(Delivery.event_id == prefix)) == 21
        print(json.dumps({"kind": "http_postgres_fixture_receipt_races", "duplicate_acks": 20,
            "redelivery_acks": 20, "jobs": 1, "retained_deliveries": 21,
            "conflicting_body_http": 409, "conflicting_identity_http": 409,
            "first_deadline_preserved": True, "limits": "Fixture only; not official coverage"}))


if __name__ == "__main__":
    asyncio.run(main())
