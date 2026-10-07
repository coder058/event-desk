"""One archived inference per free provider; local results never POST to the competition."""
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        raise RuntimeError("Provider probes require the shared PostgreSQL ledger")
    store = Store(url)
    Quotas(store).summary()
    directory = args.output_dir
    directory.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.archive, "rt", encoding="utf-8") as source:
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
