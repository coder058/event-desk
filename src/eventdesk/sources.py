"""Atomic source checkpoints depend on verified retained bytes, never a partial fetch."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.store import ConflictError, SourceBatch, SourceCapture, SourceCursor, Store


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


class Sources:
    def __init__(self, store: Store, objects: RawObjects) -> None:
        self.store, self.objects = store, objects

    def commit_batch(self, *, source: Literal["sec", "defense_contracts"], feed: str,
                     documents: list[CapturedDocument], checkpoint: dict[str, Any],
                     completed_at: datetime, expected_head: str | None) -> str:
        # Operator-specified logical feed names are not arbitrary source URLs or credentials.
        if (source not in ("sec", "defense_contracts") or
                re.fullmatch(r"[a-z][a-z0-9_.:-]*", feed) is None or completed_at.tzinfo is None):
            raise ValueError("Source feed/time invalid")
        if expected_head is not None and re.fullmatch(r"[0-9a-f]{64}", expected_head) is None:
            raise ValueError("Expected head must be a manifest digest")
        feed_key = source+":"+feed
        retained: dict[str, CapturedDocument] = {}
        for document in documents:
            # Revalidate even an internal model_copy/constructed instance before admitting provenance.
            document = CapturedDocument.model_validate(document.model_dump())
            if document.source != source or document.first_seen_at > completed_at:
                raise ValueError("Capture source/time conflicts with batch")
            if len(self.objects.read(document.content_sha256)) != document.content_bytes:
                raise ValueError("Capture length differs from retained source bytes")
            retained[canonical_hash(document.model_dump(mode="json"))] = document
        capture_hashes = sorted(retained)
        digest = canonical_hash({"feed_key": feed_key, "previous_head": expected_head,
            "completed_at": completed_at.astimezone(UTC).isoformat(),
            "checkpoint": checkpoint, "capture_hashes": capture_hashes})
        with self.store.fixture_guard(), Session(self.store.engine) as session, session.begin():
            if self.store.engine.dialect.name == "postgresql":
                # SOURCE: sorted signed 64-bit advisory keys avoid duplicate inserts/deadlocks across feeds.
                identities = ["source-feed:"+feed_key]+["source-capture:"+item for item in capture_hashes]
                keys = {int.from_bytes(hashlib.sha256(item.encode()).digest()[:8], signed=True)
                        for item in identities}
                for key in sorted(keys):
                    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
            # A retry of an already committed manifest cannot rewind a newer cursor.
            if session.get(SourceBatch, digest) is not None:
                return digest
            cursor = session.get(SourceCursor, feed_key, with_for_update=True)
            if (cursor.head if cursor else None) != expected_head:
                raise ConflictError("Source checkpoint advanced; reread before committing")
            if cursor:
                previous = session.get(SourceBatch, cursor.head)
                assert previous is not None
                if completed_at.timestamp() < previous.completed_at:
                    raise ConflictError("Source checkpoint cannot move backward in time")
            for manifest, document in retained.items():
                if session.get(SourceCapture, manifest) is None:
                    session.add(SourceCapture(manifest_hash=manifest, source=source,
                        content_hash=document.content_sha256, first_seen_at=document.first_seen_at.timestamp(),
                        accepted_at=document.accepted_at.timestamp() if document.accepted_at else None,
                        provenance=document.model_dump(mode="json")))
            session.flush()
            session.add(SourceBatch(manifest_hash=digest, feed_key=feed_key,
                completed_at=completed_at.timestamp(), previous_head=expected_head,
                checkpoint=checkpoint, capture_hashes=capture_hashes))
            session.flush()
            if cursor:
                cursor.head = digest
            else:
                session.add(SourceCursor(feed_key=feed_key, head=digest))
        return digest

    def cursor(self, source: Literal["sec", "defense_contracts"], feed: str) -> dict[str, Any] | None:
        with Session(self.store.engine) as session:
            row = session.get(SourceCursor, source+":"+feed)
            if row is None:
                return None
            batch = session.get(SourceBatch, row.head)
            assert batch is not None
            return {"head": row.head, "checkpoint": batch.checkpoint, "completed_at": batch.completed_at}

    def captured_before(self, cutoff: datetime) -> list[CapturedDocument]:
        if cutoff.tzinfo is None:
            raise ValueError("Cutoff requires timezone")
        with Session(self.store.engine) as session:
            rows = session.scalars(select(SourceCapture).where(SourceCapture.accepted_at <= cutoff.timestamp(),
                SourceCapture.first_seen_at <= cutoff.timestamp()).order_by(SourceCapture.manifest_hash))
            # Unknown acceptance is excluded by SQL; validate metadata and retained bytes again before use.
            documents = []
            for row in rows:
                document = CapturedDocument.model_validate(row.provenance)
                if (canonical_hash(row.provenance) != row.manifest_hash or
                        row.content_hash != document.content_sha256 or
                        row.first_seen_at != document.first_seen_at.timestamp() or
                        row.accepted_at != (document.accepted_at.timestamp() if document.accepted_at else None) or
                        not document.usable_before(cutoff)):
                    raise ValueError("Retained source metadata failed cutoff verification")
                if len(self.objects.read(document.content_sha256)) != document.content_bytes:
                    raise ValueError("Retained source bytes changed")
                documents.append(document)
            return documents
