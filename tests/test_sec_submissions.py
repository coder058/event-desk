import json
from datetime import UTC, datetime, timedelta

import pytest

from eventdesk.evidence import CapturedDocument, RawObjects
from eventdesk.sec_submissions import discover_submissions

# PLACEHOLDER: synthetic CIK/accessions/times test parser boundaries, not actual SEC filings.
SEEN = datetime(2026, 10, 7, 12, tzinfo=UTC)


def payload():
    return {"cik": 123, "filings": {"recent": {
        "accessionNumber": ["0000000123-26-000001", "0000000123-26-000002", "0000000123-26-000003"],
        "form": ["8-K", "4", "10-K"], "filingDate": ["2026-10-07"]*3,
        "primaryDocument": ["current.htm", "xslF345X05/ownership.xml", "annual.htm"],
        "acceptanceDateTime": ["2026-10-07T11:00:00Z", "2026-10-07T07:30:00-04:00", "2026-10-07T10:00:00Z"]},
        "files": [{"name": "CIK0000000123-submissions-001.json", "filingCount": 100}]}}


def capture(tmp_path, body, raw=None):
    objects = RawObjects(tmp_path/"objects")
    raw = json.dumps(body).encode() if raw is None else raw
    document = CapturedDocument(source="sec", source_url="https://data.sec.gov/submissions/CIK0000000123.json",
        content_sha256=objects.put(raw), content_bytes=len(raw), accepted_at=None, first_seen_at=SEEN)
    return document, objects


def test_discovery_preserves_identity_offsets_and_excludes_unsupported_forms(tmp_path):
    document, objects = capture(tmp_path, payload())
    result = discover_submissions(document, objects)
    assert len(result.references) == 2
    first, second = result.references
    assert first.accepted_at == datetime(2026, 10, 7, 11, tzinfo=UTC)
    assert second.accepted_at == datetime(2026, 10, 7, 11, 30, tzinfo=UTC)
    assert second.source_url == "https://www.sec.gov/Archives/edgar/data/123/000000012326000002/xslF345X05/ownership.xml"
    assert first.submissions_sha256 == document.content_sha256
    assert first.discovered_before(SEEN)
    assert not first.discovered_before(SEEN-timedelta(seconds=1))
    assert result.additional_history_files == ("CIK0000000123-submissions-001.json",)


def test_filing_date_and_naive_acceptance_never_become_usable_timestamps(tmp_path):
    body = payload()
    body["filings"]["recent"]["acceptanceDateTime"] = [None, "2026-10-07T07:30:00", ""]
    document, objects = capture(tmp_path, body)
    result = discover_submissions(document, objects)
    assert [value.acceptance_status for value in result.references] == ["missing", "unknown_timezone"]
    assert all(value.accepted_at is None and not value.discovered_before(SEEN) for value in result.references)


@pytest.mark.parametrize("change", ["cik", "misaligned", "future", "traversal", "encoded", "origin", "history"])
def test_corrupt_metadata_cannot_create_plausible_filing_references(tmp_path, change):
    body = payload()
    recent = body["filings"]["recent"]
    if change == "cik":
        body["cik"] = 124
    elif change == "misaligned":
        recent["filingDate"].pop()
    elif change == "future":
        recent["acceptanceDateTime"][0] = "2026-10-07T13:00:00Z"
    elif change == "traversal":
        recent["primaryDocument"][0] = "../environment"
    elif change == "encoded":
        recent["primaryDocument"][0] = "%2e%2e/file"
    elif change == "origin":
        recent["primaryDocument"][0] = "https://another.example/file"
    else:
        body["filings"]["files"][0]["name"] = "CIK0000000124-submissions-001.json"
    document, objects = capture(tmp_path, body)
    with pytest.raises(ValueError):
        discover_submissions(document, objects)


def test_duplicate_json_keys_and_conflicting_accessions_fail_closed(tmp_path):
    document, objects = capture(tmp_path, {}, raw=b'{"cik":123,"cik":124}')
    with pytest.raises(ValueError, match="duplicate"):
        discover_submissions(document, objects)
    body = payload()
    body["filings"]["recent"]["accessionNumber"][1] = body["filings"]["recent"]["accessionNumber"][0]
    document, objects = capture(tmp_path, body)
    with pytest.raises(ValueError, match="Conflicting"):
        discover_submissions(document, objects)
