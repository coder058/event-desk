"""Atomic source checkpoints depend on verified retained bytes, never a partial fetch."""
from __future__ import annotations

import hashlib
import json
import math
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


def checkpoint_copy(value: dict[str, Any]) -> dict[str, Any]:
    """Detach caller-owned nested containers before hashing or durable storage."""
    def validate(item: object) -> None:
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("Checkpoint keys must be strings")
            for child in item.values():
                validate(child)
        elif isinstance(item, list):
            for child in item:
                validate(child)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("Checkpoint must contain only JSON values")
    if not isinstance(value, dict):
        raise ValueError("Checkpoint must be a JSON object")
    validate(value)
    result: dict[str, Any] = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    return result


class Sources:
    def __init__(self, store: Store, objects: RawObjects) -> None:
        self.store, self.objects = store, objects

    @staticmethod
    def feed_key(source: Literal["sec", "defense_contracts"], feed: str) -> str:
        if source not in ("sec", "defense_contracts") or re.fullmatch(r"[a-z][a-z0-9_.:-]*", feed) is None:
            raise ValueError("Source feed invalid")
        return source+":"+feed

    def verify_capture(self, capture: SourceCapture, source: str) -> CapturedDocument:
        document = CapturedDocument.model_validate(capture.provenance)
        if (canonical_hash(capture.provenance) != capture.manifest_hash or
                capture.source != source or document.source != source or
                capture.content_hash != document.content_sha256 or
                capture.first_seen_at != document.first_seen_at.timestamp() or
                capture.accepted_at != (document.accepted_at.timestamp() if document.accepted_at else None)):
            raise ValueError("Retained source metadata failed verification")
        if len(self.objects.read(document.content_sha256)) != document.content_bytes:
            raise ValueError("Retained source bytes changed")
        return document

    def verify_batch(self, session: Session, batch: SourceBatch, feed_key: str) -> None:
        captures = batch.capture_hashes
        if (batch.feed_key != feed_key or not math.isfinite(batch.completed_at) or
                not isinstance(captures, list) or
                any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in captures) or
                captures != sorted(set(captures)) or
                (batch.previous_head is not None and re.fullmatch(r"[0-9a-f]{64}", batch.previous_head) is None)):
            raise ValueError("Retained source batch identity invalid")
        completed = datetime.fromtimestamp(batch.completed_at, UTC)
        digest = canonical_hash({"feed_key": batch.feed_key, "previous_head": batch.previous_head,
            "completed_at": completed.isoformat(), "checkpoint": checkpoint_copy(batch.checkpoint),
            "capture_hashes": captures})
        if digest != batch.manifest_hash:
            raise ValueError("Retained source batch digest changed")
        for identity in captures:
            capture = session.get(SourceCapture, identity)
            if capture is None:
                raise ValueError("Retained source batch capture missing")
            document = self.verify_capture(capture, feed_key.split(":", 1)[0])
            if document.first_seen_at > completed:
                raise ValueError("Retained source batch capture time invalid")

    def commit_batch(self, *, source: Literal["sec", "defense_contracts"], feed: str,
                     documents: list[CapturedDocument], checkpoint: dict[str, Any],
                     completed_at: datetime, expected_head: str | None) -> str:
        # Operator-specified logical feed names are not arbitrary source URLs or credentials.
        feed_key = self.feed_key(source, feed)
        if completed_at.tzinfo is None:
            raise ValueError("Source feed/time invalid")
        if expected_head is not None and re.fullmatch(r"[0-9a-f]{64}", expected_head) is None:
            raise ValueError("Expected head must be a manifest digest")
        checkpoint = checkpoint_copy(checkpoint)
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
            existing = session.get(SourceBatch, digest)
            if existing is not None:
                self.verify_batch(session, existing, feed_key)
                return digest
            cursor = session.get(SourceCursor, feed_key, with_for_update=True)
            if (cursor.head if cursor else None) != expected_head:
                raise ConflictError("Source checkpoint advanced; reread before committing")
            if cursor:
                previous = session.get(SourceBatch, cursor.head)
                if previous is None:
                    raise ValueError("Retained source head is missing")
                self.verify_batch(session, previous, feed_key)
                if completed_at.timestamp() < previous.completed_at:
                    raise ConflictError("Source checkpoint cannot move backward in time")
            for manifest, document in retained.items():
                existing_capture = session.get(SourceCapture, manifest)
                if existing_capture is None:
                    session.add(SourceCapture(manifest_hash=manifest, source=source,
                        content_hash=document.content_sha256, first_seen_at=document.first_seen_at.timestamp(),
                        accepted_at=document.accepted_at.timestamp() if document.accepted_at else None,
                        provenance=document.model_dump(mode="json")))
                else:
                    self.verify_capture(existing_capture, source)
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
        feed_key = self.feed_key(source, feed)
        with Session(self.store.engine) as session:
            row = session.get(SourceCursor, feed_key)
            if row is None:
                return None
            batch = session.get(SourceBatch, row.head)
            if batch is None:
                raise ValueError("Retained source head is missing")
            self.verify_batch(session, batch, feed_key)
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
                document = self.verify_capture(row, row.source)
                if not document.usable_before(cutoff):
                    raise ValueError("Retained source metadata failed cutoff verification")
                documents.append(document)
            return documents
