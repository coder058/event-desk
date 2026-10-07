"""Resumable recent-company SEC capture, separate from competition prediction.

Every discovered reference survives in a verified checkpoint before body reads.
Each successful body gets its own atomic checkpoint. A block, crash or limited
run cannot silently skip a filing; no all-market/history completeness is claimed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.sec_submissions import FilingReference, discover_submissions, normalize_cik
from eventdesk.sec_transport import (
    MIN_INTERVAL_SECONDS,
    PostgresSecGate,
    SecDeferred,
    SecFetchFailed,
    SecTransport,
    user_agent,
)
from eventdesk.sources import Sources
from eventdesk.store import Store


class CollectionCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["sec-recent-collection-v1"] = "sec-recent-collection-v1"
    cik: str
    latest_submissions_sha256: str
    submissions: dict[str, CapturedDocument]
    references: dict[str, FilingReference]
    bodies: dict[str, CapturedDocument]


class CollectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    cik: str
    state: Literal["recent_scope_complete", "budget_exhausted", "deferred", "fetch_failed"]
    head: str | None
    discovered: int
    captured: int
    newly_captured: int
    pending: int
    limits: str = ("Explicit company universe; supported recent forms plus retained unfinished references only. "
                   "Additional history is not downloaded. First successful body capture is retained; unchanged "
                   "accessions are not refetched to claim current bytes. No extraction, return or trading signal.")


class SecCollector:
    def __init__(self, *, transport: SecTransport, sources: Sources,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        if transport.objects.root.resolve() != sources.objects.root.resolve():
            raise ValueError("Collector and transport must share the exact raw object store")
        self.transport, self.sources, self.clock = transport, sources, clock

    def verify(self, checkpoint: CollectionCheckpoint, cik: str) -> None:
        if checkpoint.cik != cik or checkpoint.latest_submissions_sha256 not in checkpoint.submissions:
            raise ValueError("Collector checkpoint identity mismatch")
        discovered: dict[str, dict[str, FilingReference]] = {}
        for digest, document in checkpoint.submissions.items():
            if digest != document.content_sha256:
                raise ValueError("Submissions checkpoint hash mismatch")
            parsed = discover_submissions(document, self.sources.objects)
            if parsed.cik != cik:
                raise ValueError("Submissions checkpoint contains a different company")
            discovered[digest] = {reference.accession: reference for reference in parsed.references}
        for accession, reference in checkpoint.references.items():
            if (accession != reference.accession or reference.cik != cik
                    or discovered.get(reference.submissions_sha256, {}).get(accession) != reference):
                raise ValueError("Reference does not match its retained discovery bytes")
        for accession, document in checkpoint.bodies.items():
            body_reference = checkpoint.references.get(accession)
            if (body_reference is None or document.source != "sec" or document.accession != accession
                    or document.source_url != body_reference.source_url or document.form != body_reference.form
                    or document.accepted_at != body_reference.accepted_at
                    or document.first_seen_at < body_reference.discovered_at
                    or len(self.sources.objects.read(document.content_sha256)) != document.content_bytes):
                raise ValueError("Captured filing does not match its retained discovery")

    def persist(self, checkpoint: CollectionCheckpoint, head: str | None) -> str:
        self.verify(checkpoint, checkpoint.cik)
        return self.sources.commit_batch(source="sec", feed="company:"+checkpoint.cik,
            documents=[*checkpoint.submissions.values(), *checkpoint.bodies.values()],
            checkpoint=checkpoint.model_dump(mode="json"), completed_at=self.clock(), expected_head=head)

    @staticmethod
    def result(cik: str, state: Literal["recent_scope_complete", "budget_exhausted", "deferred", "fetch_failed"],
               checkpoint: CollectionCheckpoint | None, head: str | None, new: int) -> CollectionResult:
        # SOURCE: exact checkpoint counts, not estimates of SEC-wide coverage.
        discovered = len(checkpoint.references) if checkpoint else 0
        captured = len(checkpoint.bodies) if checkpoint else 0
        return CollectionResult(cik=cik, state=state, head=head, discovered=discovered, captured=captured,
                                newly_captured=new, pending=discovered-captured)

    async def collect(self, cik: str, *, max_new_filings: int) -> CollectionResult:
        cik = normalize_cik(cik)
        if isinstance(max_new_filings, bool) or not isinstance(max_new_filings, int) or max_new_filings < 1:
            raise ValueError("A positive explicit filing budget is required")
        cursor = self.sources.cursor("sec", "company:"+cik)
        head = cursor["head"] if cursor else None
        checkpoint = CollectionCheckpoint.model_validate(cursor["checkpoint"]) if cursor else None
        if checkpoint:
            self.verify(checkpoint, cik)  # Corrupt/missing bytes fail before another network read.
        try:
            fetched = await self.transport.submissions(cik)
        except SecDeferred:
            return self.result(cik, "deferred", checkpoint, head, 0)
        except SecFetchFailed:
            return self.result(cik, "fetch_failed", checkpoint, head, 0)
        if checkpoint is None:
            checkpoint = CollectionCheckpoint(cik=cik, latest_submissions_sha256=fetched.content_sha256,
                submissions={}, references={}, bodies={})
        # Preserve the earliest observation of identical metadata bytes, rather than rewriting discovery time.
        document = checkpoint.submissions.setdefault(fetched.content_sha256, fetched)
        discovery = discover_submissions(document, self.sources.objects)
        for reference in discovery.references:
            previous = checkpoint.references.get(reference.accession)
            if previous is not None:
                # Later snapshots have a different discovery hash/time. Filing identity may not silently change.
                excluded = {"submissions_sha256", "discovered_at"}
                if previous.model_dump(exclude=excluded) != reference.model_dump(exclude=excluded):
                    raise ValueError("Previously discovered accession changed; explicit review required")
            else:
                checkpoint.references[reference.accession] = reference
        checkpoint.latest_submissions_sha256 = document.content_sha256
        head = self.persist(checkpoint, head)  # Discovery and all pending references survive a crash here.
        new = 0  # SOURCE: neutral counter starts at zero; increment only after a successful durable body commit.
        for accession in sorted(checkpoint.references):
            if accession in checkpoint.bodies:
                continue
            if new >= max_new_filings:
                return self.result(cik, "budget_exhausted", checkpoint, head, new)
            # SOURCE: the existing project gate's minimum spacing; it still checks durable cooldown/exclusion.
            await asyncio.sleep(MIN_INTERVAL_SECONDS)
            try:
                body = await self.transport.filing(checkpoint.references[accession])
            except SecDeferred:
                return self.result(cik, "deferred", checkpoint, head, new)
            except SecFetchFailed:
                return self.result(cik, "fetch_failed", checkpoint, head, new)
            checkpoint.bodies[accession] = body
            head = self.persist(checkpoint, head)
            new += 1
        return self.result(cik, "recent_scope_complete", checkpoint, head, new)


def checkpoint_summary(value: dict[str, Any]) -> dict[str, Any]:
    """Safe coverage metadata; no document contents, contact, source text or model claim."""
    checkpoint = CollectionCheckpoint.model_validate(value)
    return {"cik": checkpoint.cik, "discovered": len(checkpoint.references), "captured": len(checkpoint.bodies),
            "pending": len(checkpoint.references)-len(checkpoint.bodies),
            "unknown_acceptance": sum(reference.accepted_at is None for reference in checkpoint.references.values()),
            "latest_submissions_sha256": checkpoint.latest_submissions_sha256}


async def collect_configured(*, ciks: list[str], objects_root: Path, max_new_filings: int) -> list[CollectionResult]:
    # Validate the identity before opening a database connection or creating object directories.
    contact = user_agent(os.environ.get("SEC_USER_AGENT", ""))
    database = os.environ.get("DATABASE_URL", "")
    if not database:
        raise ValueError("DATABASE_URL is required for the shared collection ledger")
    normalized = sorted({normalize_cik(cik) for cik in ciks})
    if not normalized:
        raise ValueError("An explicit nonempty SEC company universe is required")
    if isinstance(max_new_filings, bool) or not isinstance(max_new_filings, int) or max_new_filings < 1:
        raise ValueError("A positive explicit filing budget is required")
    store = Store(database)
    try:
        gate = PostgresSecGate(store)
        objects = RawObjects(objects_root)
        async with SecTransport(contact=contact, gate=gate, objects=objects) as transport:
            collector = SecCollector(transport=transport, sources=Sources(store, objects))
            results = []
            for cik in normalized:
                results.append(await collector.collect(cik, max_new_filings=max_new_filings))
            return results
    finally:
        store.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture explicitly selected SEC companies with durable partial progress")
    parser.add_argument("--cik", nargs="+", required=True)
    parser.add_argument("--objects-root", type=Path, required=True)
    parser.add_argument("--max-new-filings", type=int, required=True,
                        help="Operational per-company/run budget; this is not a calibrated market parameter")
    args = parser.parse_args()
    try:
        results = asyncio.run(collect_configured(ciks=args.cik, objects_root=args.objects_root,
                                               max_new_filings=args.max_new_filings))
    except Exception as error:
        # Do not print exception text: an injected database/HTTP error may contain credentials or contact details.
        print(json.dumps({"state": "configuration_or_capture_failed", "error_type": type(error).__name__}))
        raise SystemExit(1) from None  # SOURCE: conventional nonzero command failure status.
    print(json.dumps([result.model_dump(mode="json") for result in results]))
    if any(result.state != "recent_scope_complete" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
