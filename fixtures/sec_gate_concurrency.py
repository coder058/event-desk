"""Actual PostgreSQL SEC reader exclusion/cooldown; no SEC network request."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from eventdesk.sec_transport import PostgresSecGate, SecDeferred
from eventdesk.store import Store


def main() -> None:
    if os.getenv("EVENTDESK_FIXTURE_MODE", "false").lower() != "true":
        raise RuntimeError("Refusing synthetic SEC gate states against production")
    store = Store(os.environ["DATABASE_URL"])
    clock = [time.time()]
    gate = PostgresSecGate(store, lambda: clock[0])
    # PLACEHOLDER: synthetic request identity; the fixture never contacts SEC.
    url = "https://data.sec.gov/submissions/CIK0000000123.json"
    def acquire(_):
        try:
            return gate.acquire(url)
        except SecDeferred:
            return None
    # GUESS: four contenders force session-lock exclusion, not throughput capacity. # UNCALIBRATED GUESS
    with ThreadPoolExecutor(max_workers=4) as pool:
        permits = [value for value in pool.map(acquire, range(4)) if value is not None]
    assert len(permits) == 1
    # PLACEHOLDER: synthetic cooldown tests durability across a fresh connection/gate.
    permits[0].finish("fixture_no_network", None, None, 60)
    new = PostgresSecGate(Store(os.environ["DATABASE_URL"]), lambda: clock[0])
    try:
        new.acquire(url)
    except SecDeferred:
        pass
    else:
        raise AssertionError("Shared cooldown was reset")
    clock[0] += 61  # SOURCE: advance beyond this fixture's sixty-second cooldown.
    later = new.acquire(url)
    later.finish("fixture_no_network", None, None, 0)
    print(json.dumps({"kind": "postgresql_sec_gate_fixture", "contenders": 4,
        "simultaneous_admissions": 1, "persisted_cooldown_blocks": True,
        "admitted_after_cooldown": True, "external_requests": 0,
        "limits": "Synthetic request/clock; not actual SEC access, throughput or daily ingestion"}))


if __name__ == "__main__":
    main()
