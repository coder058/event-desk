"""One archived inference per free provider; local results never POST to the competition."""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from eventdesk.llm import PROMPT_HASH, Router, providers_from_env
from eventdesk.materials import input_hash, select_items
from eventdesk.quotas import Quotas
from eventdesk.store import Store


async def run() -> None:
    env_path = Path.home() / ".eventdesk/.env"
    for line in env_path.read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            os.environ[name.strip()] = value.strip().strip('"').strip("'")
    directory = Path("private")
    directory.mkdir(exist_ok=True)
    store = Store("sqlite:///private/provider-probe.sqlite")
    # Importing provider models above registers the quota tables for this private offline probe DB.
    store.initialize_fixture()
    with gzip.open(Path.home() / ".eventdesk/research/archive/2026Q2.jsonl.gz", "rt", encoding="utf-8") as source:
        record = json.loads(next(source))
    items = select_items(record)
    results = []
    async with httpx.AsyncClient() as http:
        for provider in providers_from_env():
            result = await Router(Quotas(store), http, (provider,)).analyze(items, time.time() + 300)
            saved = {"date": datetime.now(UTC).isoformat(), "event_id": record["event_id"],
                     "provider": provider.name, "model": provider.model,
                     "prompt_hash": PROMPT_HASH, "inputs_hash": input_hash(items),
                     "latency_ms": result.latency_ms, "attempts": result.attempts,
                     "analysis": result.analysis.model_dump() if result.analysis else None}
            results.append(saved)
            # Only metadata, no credentials/request headers/response error bodies.
            print(json.dumps({k: saved[k] for k in ["provider", "model", "latency_ms", "attempts"]}))
    (directory / "provider-probe.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(run())
