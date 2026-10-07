"""Actual PostgreSQL capture/resume with mocked SEC HTTP, fixture environment only."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import httpx

from eventdesk.evidence import RawObjects
from eventdesk.sec_collection import SecCollector
from eventdesk.sec_transport import MIN_INTERVAL_SECONDS, PostgresSecGate, SecTransport
from eventdesk.sources import Sources
from eventdesk.store import Store


async def run() -> None:
    if os.getenv("EVENTDESK_FIXTURE_MODE", "false").lower() != "true":
        raise RuntimeError("Refusing synthetic SEC collection against production")
    database = os.environ["DATABASE_URL"]
    store = Store(database)
    if store.engine.dialect.name != "postgresql":
        raise RuntimeError("Collection integration requires PostgreSQL")
    # PLACEHOLDER: fictional company/accessions, not actual SEC filings or a coverage universe.
    cik = "0000000123"
    accessions = ["0000000123-20-000001", "0000000123-20-000002"]
    metadata = {"cik": 123, "filings": {"recent": {"accessionNumber": accessions,
        "form": ["8-K", "4"], "filingDate": ["2020-01-01", "2020-01-01"],
        "primaryDocument": ["first.htm", "second.xml"],
        "acceptanceDateTime": ["2020-01-01T12:00:00Z", "2020-01-01T13:00:00Z"]}, "files": []}}
    calls: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "/submissions/" in url:
            return httpx.Response(200, json=metadata)
        if url.endswith("/first.htm") or url.endswith("/second.xml"):
            return httpx.Response(200, content=("Synthetic body: "+url.rsplit("/", 1)[1]).encode())
        raise AssertionError("Unexpected mocked collection URL")
    with tempfile.TemporaryDirectory(prefix="sec-collection-") as temporary:
        objects = RawObjects(Path(temporary)/"objects")
        sources = Sources(store, objects)
        if sources.cursor("sec", "company:"+cik) is not None:
            raise RuntimeError("This fixture requires a fresh disposable collection ledger")
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            collector = SecCollector(sources=sources, transport=SecTransport(contact="EventDesk fixture@example.test",
                gate=PostgresSecGate(store), objects=objects, http=http))
            first = await collector.collect(cik, max_new_filings=1)
            assert first.state == "budget_exhausted" and first.pending == 1 and first.captured == 1
            checkpoint = sources.cursor("sec", "company:"+cik)
            assert checkpoint is not None
            first_seen = checkpoint["checkpoint"]["bodies"][accessions[0]]["first_seen_at"]
            # SOURCE: the same durable gate spacing, including between two operator runs.
            await asyncio.sleep(MIN_INTERVAL_SECONDS)
            restarted_store = Store(database)
            try:
                restarted = SecCollector(sources=Sources(restarted_store, objects),
                    transport=SecTransport(contact="EventDesk fixture@example.test", objects=objects,
                                           gate=PostgresSecGate(restarted_store), http=http))
                second = await restarted.collect(cik, max_new_filings=1)
                assert second.state == "recent_scope_complete" and second.captured == 2 and second.pending == 0
                current = restarted.sources.cursor("sec", "company:"+cik)
                assert current is not None
                assert current["checkpoint"]["bodies"][accessions[0]]["first_seen_at"] == first_seen
                assert len([url for url in calls if url.endswith("/first.htm")]) == 1
            finally:
                restarted_store.engine.dispose()
    store.engine.dispose()
    print(json.dumps({"kind": "postgresql_sec_collection_fixture", "mock_http_requests": len(calls),
        "external_sec_requests": 0, "retained_bodies": second.captured, "remaining_references": second.pending,
        "limits": "Actual PostgreSQL/pacing and mock HTTP. Synthetic documents, no real SEC collection."}))


if __name__ == "__main__":
    asyncio.run(run())
