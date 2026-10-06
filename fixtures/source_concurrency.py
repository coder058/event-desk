"""Real PostgreSQL source checkpoint races, only in the disposable fixture project."""
from __future__ import annotations

import json
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.sources import Sources
from eventdesk.store import SourceCapture, Store


def main() -> None:
    if os.getenv("EVENTDESK_FIXTURE_MODE", "false").lower() != "true":
        raise RuntimeError("Refusing source races against production")
    store = Store(os.environ["DATABASE_URL"])
    if store.engine.dialect.name != "postgresql":
        raise RuntimeError("This integration probe requires actual PostgreSQL")
    prefix = "fixture-"+str(time.time_ns())
    with tempfile.TemporaryDirectory(prefix="source-race-") as temporary:
        objects = RawObjects(Path(temporary)/"objects")
        raw = b"Synthetic fixture-only raw evidence: "+prefix.encode()
        now = datetime.now(UTC)
        document = CapturedDocument(source="sec", source_url="https://www.sec.gov/Archives/edgar/fixture.txt",
            content_sha256=objects.put(raw), content_bytes=len(raw), form="8-K", accepted_at=now, first_seen_at=now)
        sources = Sources(store, objects)
        args = {"source": "sec", "feed": prefix, "documents": [document],
                "checkpoint": {"fixture_only": True}, "completed_at": now, "expected_head": None}
        # GUESS: eight attempts/four threads force identity races; not a capacity or filing-frequency claim. # UNCALIBRATED GUESS
        with ThreadPoolExecutor(max_workers=4) as pool:
            heads = list(pool.map(lambda _: sources.commit_batch(**args), range(8)))
            cross_feed = list(pool.map(lambda i: sources.commit_batch(**{**args, "feed": prefix+"-"+str(i)}), range(4)))
        assert len(set(heads)) == 1 and len(set(cross_feed)) == 4
        with Session(store.engine) as session:
            assert session.scalar(select(func.count()).select_from(SourceCapture)
                .where(SourceCapture.content_hash == document.content_sha256)) == 1
        assert sources.cursor("sec", prefix)["head"] == heads[0]
        assert document in sources.captured_before(now)
        print(json.dumps({"kind": "postgresql_source_checkpoint_fixture", "duplicate_commits": len(heads),
            "cross_feed_commits": len(cross_feed), "retained_capture_rows": 1,
            "limits": "Synthetic bytes in disposable fixture database; no external requests or actual SEC ingestion"}))


if __name__ == "__main__":
    main()
