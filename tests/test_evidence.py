import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from eventdesk.evidence import CapturedDocument, QuotedEvidence, RawObjects


def document(raw):
    # PLACEHOLDER: synthetic document/times exercise provenance, not an observed filing.
    return CapturedDocument(source="sec", source_url="https://www.sec.gov/Archives/edgar/fixture.txt",
        content_sha256=hashlib.sha256(raw).hexdigest(), content_bytes=len(raw),
        accepted_at=datetime.fromisoformat("2026-10-12T13:00:00Z"),
        first_seen_at=datetime.fromisoformat("2026-10-12T13:00:01Z"), form="8-K")


def test_raw_objects_are_immutable_content_verified_and_not_path_inputs(tmp_path):
    store = RawObjects(tmp_path/"raw")
    raw = b"Official raw source bytes\x00\xff"
    with ThreadPoolExecutor(max_workers=4) as pool:
        # PLACEHOLDER: concurrent retransmissions verify atomic deduplication.
        hashes = list(pool.map(lambda _: store.put(raw), range(12)))
    assert len(set(hashes)) == 1
    assert store.read(hashes[0]) == raw
    assert not list((tmp_path/"raw").rglob(".capture-*"))
    with pytest.raises(ValueError):
        store.read("../../other")
    (tmp_path/"raw"/hashes[0][:2]/hashes[0]).write_bytes(b"corruption")
    with pytest.raises(ValueError):
        store.put(raw)
    with pytest.raises(ValueError):
        store.read(hashes[0])


def test_later_capture_or_unknown_acceptance_is_not_point_in_time_proof():
    captured = document(b"fixture")
    before = datetime.fromisoformat("2026-10-12T12:59:59Z")
    between = datetime.fromisoformat("2026-10-12T13:00:00.5Z")
    after = datetime.fromisoformat("2026-10-12T13:00:02Z")
    assert not captured.usable_before(before)
    assert not captured.usable_before(between)
    assert captured.usable_before(after)
    unknown = CapturedDocument(**{**captured.model_dump(), "accepted_at": None})
    assert not unknown.usable_before(after)
    with pytest.raises(ValueError):
        captured.usable_before(datetime(2026, 10, 12))
    with pytest.raises(ValueError):
        CapturedDocument(**{**captured.model_dump(), "accepted_at": after})
    with pytest.raises(ValueError):
        CapturedDocument(**{**captured.model_dump(), "source_url": "https://www.sec.gov@fixture.invalid/"})


def test_quotes_are_exact_retained_text_with_document_and_text_hashes(tmp_path):
    text = "Revenue increased. Guidance was maintained."
    captured = document(text.encode())
    objects = RawObjects(tmp_path/"raw")
    objects.put(text.encode())
    quote = QuotedEvidence(document_sha256=captured.content_sha256,
        text_sha256=hashlib.sha256(text.encode()).hexdigest(), start=0, end=len("Revenue increased."),
        quote="Revenue increased.")
    quote.verify(captured, text, objects)
    with pytest.raises(ValueError):
        quote.verify(captured, text.replace("increased", "declined"), objects)
    with pytest.raises(ValueError):
        QuotedEvidence(**{**quote.model_dump(), "quote": "Revenue strongly increased."}).verify(captured, text, objects)
    unrelated = "Unrelated fake source."
    fabricated = QuotedEvidence(document_sha256=captured.content_sha256,
        text_sha256=hashlib.sha256(unrelated.encode()).hexdigest(), start=0, end=len(unrelated), quote=unrelated)
    with pytest.raises(ValueError):
        fabricated.verify(captured, unrelated, objects)
