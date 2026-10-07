"""Label-blind archive evidence collection; no competition submissions."""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import logging
import math
import os
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx

from eventdesk.llm import PROMPT_HASH, Router, providers_from_env, reservation_tokens
from eventdesk.materials import input_hash, select_items
from eventdesk.quotas import Quotas
from eventdesk.store import Store


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", choices=["2026Q2", "2026Q3"], required=True)
    parser.add_argument("--provider", choices=["gemini", "groq"], required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    # SOURCE: exact IDs in authenticated model inventory and official free-tier pricing on 2026-10-05.
    parser.add_argument("--model", choices=["gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
                                          "gemini-3.8-flash", "openai/gpt-oss-120b"])
    # GUESS: caller-bounded local quota waiting; zero preserves immediate-stop behavior. # UNCALIBRATED GUESS
    parser.add_argument("--wait-local-seconds", type=float, default=0)
    args = parser.parse_args()
    if args.count <= 0 or not math.isfinite(args.wait_local_seconds) or args.wait_local_seconds < 0:
        raise ValueError("Collection count/wait must be finite and nonnegative (count positive)")
    # SOURCE: research and live calls must debit the same migrated PostgreSQL ledger.
    # No automatic local ledger or key-file loading can silently create a second budget.
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        raise RuntimeError("Research calls require the shared PostgreSQL DATABASE_URL")
    store = Store(url)
    Quotas(store).summary()  # Verify migrated connectivity before loading inputs or calling a provider.
    directory = args.output_dir
    directory.mkdir(parents=True, exist_ok=True)
    archive = args.archive_dir / (args.quarter + ".jsonl.gz")
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
            now = time.time()
            admission = router.quotas.next_admission(provider.name, reservation_tokens(items), provider.limits, now)
            if admission is None:
                print(json.dumps({"provider": provider.name, "state": "request_exceeds_local_budget"}), flush=True)
                break
            if admission > now:
                state = router.quotas.summary().get(provider.name, {})
                # A recorded provider outage/cooldown is an external stop, not a local scheduling opportunity.
                if (state.get("cooldown_until", 0) > now or admission-now > args.wait_local_seconds):
                    print(json.dumps({"provider": provider.name, "state": "admission_deferred",
                                      "local_wait_seconds": admission-now}), flush=True)
                    break
                print(json.dumps({"provider": provider.name, "state": "waiting_local_window",
                                  "local_wait_seconds": admission-now}), flush=True)
                await asyncio.sleep(admission-now)
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
