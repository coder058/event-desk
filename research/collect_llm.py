"""Label-blind archive evidence collection; no competition submissions."""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import logging
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx

from eventdesk.llm import PROMPT_HASH, Router, providers_from_env
from eventdesk.materials import input_hash, select_items
from eventdesk.quotas import Quotas
from eventdesk.store import Store


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", choices=["2026Q2", "2026Q3"], required=True)
    parser.add_argument("--provider", choices=["gemini", "groq"], required=True)
    parser.add_argument("--count", type=int, required=True)
    # SOURCE: exact IDs in authenticated model inventory and official free-tier pricing on 2026-10-05.
    parser.add_argument("--model", choices=["gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
                                          "gemini-3.8-flash", "openai/gpt-oss-120b"])
    args = parser.parse_args()
    for line in (Path.home() / ".eventdesk/.env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            os.environ[name.strip()] = value.strip().strip('"').strip("'")
    directory = Path("private")
    directory.mkdir(exist_ok=True)
    store = Store("sqlite:///private/provider-probe.sqlite")
    store.initialize_fixture()
    archive = Path.home() / ".eventdesk/research/archive" / (args.quarter + ".jsonl.gz")
    with gzip.open(archive, "rt", encoding="utf-8") as source:
        records = [json.loads(line) for line in source]
    # SOURCE: deterministic label-blind chronological sample, not best-return selection.
    records.sort(key=lambda record: (record["event_datetime"], record["event_id"]))
    provider = next(provider for provider in providers_from_env() if provider.name == args.provider)
    if args.model:
        if (args.provider == "gemini") != args.model.startswith("gemini-"):
            raise ValueError("Provider/model mismatch")
        provider = replace(provider, model=args.model)
    output = directory / (f"llm-{args.provider}-{args.quarter}.jsonl" if args.model is None
                          else f"llm-{args.provider}-{provider.model.replace('/', '_')}-{args.quarter}.jsonl")
    existing = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] if output.exists() else []
    completed = {result["event_id"] for result in existing
                 if result.get("analysis") and result["prompt_hash"] == PROMPT_HASH
                 and result["model"] == provider.model}
    count = 0
    async with httpx.AsyncClient() as http:
        router = Router(Quotas(store), http, (provider,))
        for record in records:
            if record["event_id"] in completed:
                continue
            items = select_items(record)
            result = await router.analyze(items, time.time() + 300)
            saved = {"date": datetime.now(UTC).isoformat(), "event_id": record["event_id"],
                     "quarter": args.quarter, "provider": provider.name, "model": provider.model,
                     "prompt_hash": PROMPT_HASH, "inputs_hash": input_hash(items),
                     "latency_ms": result.latency_ms, "attempts": result.attempts,
                     "analysis": result.analysis.model_dump() if result.analysis else None}
            with output.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(saved) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            print(json.dumps({"event_id": record["event_id"], "provider": provider.name,
                              "validated": result.analysis is not None, "attempts": result.attempts}), flush=True)
            if result.analysis is None:
                # Do not spin through the whole archive during a provider outage/quota block.
                break
            count += 1
            if count >= args.count:
                break
            # SOURCE: configured request-per-minute budget, with a strict caller limit on this calibration run.
            await asyncio.sleep(60 / provider.limits.requests_minute)


if __name__ == "__main__":
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main())
