import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.sources import Sources, canonical_hash
from eventdesk.store import ConflictError, SourceBatch, SourceCapture, SourceCursor, Store


def setup_sources(store, tmp_path):
    # PLACEHOLDER: synthetic source bytes and times; not an actual SEC filing or ingestion.
    objects = RawObjects(tmp_path/"objects")
    raw = b"Synthetic official-shaped source"
    now = datetime.fromisoformat("2026-10-12T13:00:02Z")
    document = CapturedDocument(source="sec", source_url="https://www.sec.gov/Archives/edgar/fixture.txt",
        content_sha256=objects.put(raw), content_bytes=len(raw), accepted_at=now-timedelta(seconds=2),
        first_seen_at=now-timedelta(seconds=1), form="8-K")
    return Sources(store, objects), document, now


def test_source_batch_is_idempotent_and_cannot_rewind_cursor(store, tmp_path):
    sources, document, now = setup_sources(store, tmp_path)
    args = {"source": "sec", "feed": "fixture", "documents": [document],
            "checkpoint": {"offset": "fixture-a"}, "completed_at": now, "expected_head": None}
    with ThreadPoolExecutor(max_workers=4) as pool:
        heads = list(pool.map(lambda _: sources.commit_batch(**args), range(8)))
    assert len(set(heads)) == 1
    first = heads[0]
    second = sources.commit_batch(**{**args, "expected_head": first,
        "completed_at": now+timedelta(seconds=1), "checkpoint": {"offset": "fixture-b"}})
    assert sources.commit_batch(**args) == first
    restarted = Sources(Store(str(store.engine.url)), sources.objects)
    assert restarted.cursor("sec", "fixture")["head"] == second
    assert restarted.captured_before(now) == [document]
    with Session(store.engine) as session:
        assert session.scalar(select(func.count()).select_from(SourceCapture)) == 1
        assert session.scalar(select(func.count()).select_from(SourceBatch)) == 2
        assert session.scalar(select(func.count()).select_from(SourceCursor)) == 1
    with pytest.raises(ConflictError):
        sources.commit_batch(**{**args, "completed_at": now+timedelta(seconds=3)})
    with pytest.raises(ConflictError):
        sources.commit_batch(**{**args, "expected_head": second})


def test_missing_or_corrupt_object_cannot_advance_checkpoint(store, tmp_path):
    sources, document, now = setup_sources(store, tmp_path)
    args = {"source": "sec", "feed": "fixture", "documents": [document],
            "checkpoint": {}, "completed_at": now, "expected_head": None}
    missing = document.model_copy(update={"content_sha256": hashlib.sha256(b"not stored").hexdigest()})
    with pytest.raises(FileNotFoundError):
        sources.commit_batch(**{**args, "documents": [document, missing]})
    assert sources.cursor("sec", "fixture") is None
    with Session(store.engine) as session:
        assert session.scalar(select(func.count()).select_from(SourceCapture)) == 0
    path = sources.objects.root/document.content_sha256[:2]/document.content_sha256
    path.write_bytes(b"changed")
    with pytest.raises(ValueError):
        sources.commit_batch(**args)
    assert sources.cursor("sec", "fixture") is None


def test_cutoff_query_excludes_late_capture_and_unknown_acceptance(store, tmp_path):
    sources, document, now = setup_sources(store, tmp_path)
    unknown = CapturedDocument(**{**document.model_dump(), "accepted_at": None})
    late = CapturedDocument(**{**document.model_dump(), "first_seen_at": now+timedelta(seconds=1)})
    sources.commit_batch(source="sec", feed="fixture", documents=[document, unknown, late],
        checkpoint={}, completed_at=now+timedelta(seconds=2), expected_head=None)
    assert sources.captured_before(now) == [document]
    assert sources.captured_before(now+timedelta(seconds=3)) == sorted([document, late],
        key=lambda item: canonical_hash(item.model_dump(mode="json")))
    with pytest.raises(ValueError):
        sources.captured_before(now.replace(tzinfo=None))


def test_checkpoint_transaction_failure_rolls_back_all_metadata(store, tmp_path):
    sources, document, now = setup_sources(store, tmp_path)
    def fail_cursor(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO source_cursors"):
            raise RuntimeError("Injected durable checkpoint failure")
    event.listen(store.engine, "before_cursor_execute", fail_cursor)
    try:
        with pytest.raises(RuntimeError, match="Injected"):
            sources.commit_batch(source="sec", feed="fixture", documents=[document],
                checkpoint={}, completed_at=now, expected_head=None)
    finally:
        event.remove(store.engine, "before_cursor_execute", fail_cursor)
    with Session(store.engine) as session:
        assert session.scalar(select(func.count()).select_from(SourceCapture)) == 0
        assert session.scalar(select(func.count()).select_from(SourceBatch)) == 0
    assert sources.cursor("sec", "fixture") is None
    assert sources.objects.read(document.content_sha256)  # Only an unreferenced immutable blob remains.
    sources.commit_batch(source="sec", feed="fixture", documents=[document],
        checkpoint={}, completed_at=now, expected_head=None)
    assert sources.cursor("sec", "fixture") is not None
