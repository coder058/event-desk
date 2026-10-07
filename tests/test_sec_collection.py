import asyncio
import json

import httpx
import pytest

from eventdesk.evidence import RawObjects
from eventdesk.sec_collection import SecCollector, checkpoint_summary
from eventdesk.sec_transport import SecDeferred, SecTransport
from eventdesk.sources import Sources
from eventdesk.store import Store

# PLACEHOLDER: synthetic company/filing identities and source responses. No SEC requests or coverage claims.
CIK = "0000000123"
ACCESSIONS = ["0000000123-26-000001", "0000000123-26-000002"]


def metadata(*, empty=False, changed=False, unknown=False):
    return {"cik": 123, "filings": {"recent": {
        "accessionNumber": [] if empty else ACCESSIONS,
        "form": [] if empty else ["8-K", "4"],
        "filingDate": [] if empty else ["2026-10-06", "2026-10-06"],
        "primaryDocument": [] if empty else ["changed.htm" if changed else "current.htm", "xsl/ownership.xml"],
        "acceptanceDateTime": [] if empty else [None if unknown else "2026-10-06T11:00:00Z", "2026-10-06T12:00:00Z"]},
        "files": []}}


class FixtureGate:
    def __init__(self):
        self.defer_body = False

    def acquire(self, url):
        if self.defer_body and "/Archives/" in url:
            raise SecDeferred("fixture blocked")
        return self

    def finish(self, *args):
        pass


def fixture(store, tmp_path, monkeypatch):
    import eventdesk.sec_collection as module
    # PLACEHOLDER: mocked transport has no actual pacing/capacity; no synthetic test sleeps are needed.
    monkeypatch.setattr(module, "MIN_INTERVAL_SECONDS", 0)
    objects = RawObjects(tmp_path/"objects")
    sources = Sources(store, objects)
    calls = []
    responses = {"metadata": metadata(), "second_status": 200}
    gate = FixtureGate()
    def handler(request):
        url = str(request.url)
        calls.append(url)
        if "/submissions/" in url:
            return httpx.Response(200, content=json.dumps(responses["metadata"]).encode())
        if url.endswith("/current.htm"):
            return httpx.Response(200, content=b"Synthetic retained 8-K body")
        if url.endswith("/xsl/ownership.xml"):
            return httpx.Response(responses["second_status"], content=b"Synthetic retained Form 4 body")
        raise AssertionError("Unexpected source URL")
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = SecTransport(contact="EventDesk fixture@example.test", gate=gate, objects=objects, http=http)
    return SecCollector(transport=transport, sources=sources), http, sources, calls, responses, gate


def test_budget_restart_retains_pending_filings_even_when_recent_metadata_no_longer_lists_them(
        store, tmp_path, monkeypatch):
    collector, http, sources, calls, responses, _ = fixture(store, tmp_path, monkeypatch)
    async def run():
        first = await collector.collect(CIK, max_new_filings=1)
        assert first.state == "budget_exhausted" and first.captured == first.pending == 1
        first_time = sources.cursor("sec", "company:"+CIK)["checkpoint"]["bodies"][ACCESSIONS[0]]["first_seen_at"]
        responses["metadata"] = metadata(empty=True)
        restarted = SecCollector(transport=collector.transport,
            sources=Sources(Store(str(store.engine.url)), sources.objects))
        second = await restarted.collect(CIK, max_new_filings=1)
        assert second.state == "recent_scope_complete" and second.captured == 2 and second.pending == 0
        checkpoint = sources.cursor("sec", "company:"+CIK)["checkpoint"]
        assert checkpoint["bodies"][ACCESSIONS[0]]["first_seen_at"] == first_time
        assert checkpoint_summary(checkpoint)["discovered"] == 2
        assert len([url for url in calls if "/Archives/" in url]) == 2
        await http.aclose()
    asyncio.run(run())


def test_blocked_filing_remains_pending_and_does_not_erase_successful_prefix(store, tmp_path, monkeypatch):
    collector, http, sources, calls, responses, _ = fixture(store, tmp_path, monkeypatch)
    async def run():
        responses["second_status"] = 503
        result = await collector.collect(CIK, max_new_filings=2)
        assert result.state == "fetch_failed" and result.captured == result.pending == 1
        responses["second_status"] = 200
        result = await collector.collect(CIK, max_new_filings=2)
        assert result.state == "recent_scope_complete" and result.newly_captured == 1
        assert len([url for url in calls if url.endswith("/current.htm")]) == 1
        assert len(sources.cursor("sec", "company:"+CIK)["checkpoint"]["bodies"]) == 2
        await http.aclose()
    asyncio.run(run())


def test_deferred_gate_preserves_discovery_without_claiming_body_capture(store, tmp_path, monkeypatch):
    collector, http, sources, calls, _, gate = fixture(store, tmp_path, monkeypatch)
    async def run():
        gate.defer_body = True
        result = await collector.collect(CIK, max_new_filings=2)
        assert result.state == "deferred" and result.captured == 0 and result.pending == 2
        assert len(calls) == 1
        assert checkpoint_summary(sources.cursor("sec", "company:"+CIK)["checkpoint"])["pending"] == 2
        await http.aclose()
    asyncio.run(run())


def test_corrupt_body_blocks_restart_before_another_source_request(store, tmp_path, monkeypatch):
    collector, http, sources, calls, _, _ = fixture(store, tmp_path, monkeypatch)
    async def run():
        await collector.collect(CIK, max_new_filings=1)
        digest = sources.cursor("sec", "company:"+CIK)["checkpoint"]["bodies"][ACCESSIONS[0]]["content_sha256"]
        (sources.objects.root/digest[:2]/digest).write_bytes(b"corrupt")
        before = list(calls)
        with pytest.raises(ValueError):
            await collector.collect(CIK, max_new_filings=2)
        assert calls == before
        await http.aclose()
    asyncio.run(run())


def test_changed_accession_identity_cannot_replace_earlier_discovery(store, tmp_path, monkeypatch):
    collector, http, sources, _, responses, _ = fixture(store, tmp_path, monkeypatch)
    async def run():
        await collector.collect(CIK, max_new_filings=1)
        first = sources.cursor("sec", "company:"+CIK)
        responses["metadata"] = metadata(changed=True)
        with pytest.raises(ValueError, match="accession changed"):
            await collector.collect(CIK, max_new_filings=2)
        assert sources.cursor("sec", "company:"+CIK) == first
        await http.aclose()
    asyncio.run(run())


def test_unknown_acceptance_body_is_retained_but_excluded_from_point_in_time_features(store, tmp_path, monkeypatch):
    from datetime import UTC, datetime
    collector, http, sources, _, responses, _ = fixture(store, tmp_path, monkeypatch)
    async def run():
        responses["metadata"] = metadata(unknown=True)
        result = await collector.collect(CIK, max_new_filings=2)
        assert result.state == "recent_scope_complete" and result.captured == 2
        assert checkpoint_summary(sources.cursor("sec", "company:"+CIK)["checkpoint"])["unknown_acceptance"] == 1
        usable = sources.captured_before(datetime.now(UTC))
        assert [document.accession for document in usable] == [ACCESSIONS[1]]
        await http.aclose()
    asyncio.run(run())


def test_crash_after_discovery_commit_can_resume_without_losing_pending_references(store, tmp_path, monkeypatch):
    collector, http, sources, calls, _, _ = fixture(store, tmp_path, monkeypatch)
    persist = collector.persist
    def crash_after_commit(checkpoint, head):
        persist(checkpoint, head)
        raise RuntimeError("Injected process exit after durable discovery")
    async def run():
        monkeypatch.setattr(collector, "persist", crash_after_commit)
        with pytest.raises(RuntimeError, match="Injected"):
            await collector.collect(CIK, max_new_filings=2)
        assert checkpoint_summary(sources.cursor("sec", "company:"+CIK)["checkpoint"])["pending"] == 2
        monkeypatch.setattr(collector, "persist", persist)
        result = await collector.collect(CIK, max_new_filings=2)
        assert result.captured == 2 and result.pending == 0
        assert len([url for url in calls if "/Archives/" in url]) == 2
        await http.aclose()
    asyncio.run(run())


def test_crash_after_body_commit_does_not_download_that_body_again(store, tmp_path, monkeypatch):
    collector, http, sources, calls, _, _ = fixture(store, tmp_path, monkeypatch)
    persist = collector.persist
    def crash_after_body_commit(checkpoint, head):
        result = persist(checkpoint, head)
        if checkpoint.bodies:
            raise RuntimeError("Injected process exit after durable body")
        return result
    async def run():
        monkeypatch.setattr(collector, "persist", crash_after_body_commit)
        with pytest.raises(RuntimeError, match="Injected"):
            await collector.collect(CIK, max_new_filings=2)
        assert checkpoint_summary(sources.cursor("sec", "company:"+CIK)["checkpoint"])["captured"] == 1
        monkeypatch.setattr(collector, "persist", persist)
        result = await collector.collect(CIK, max_new_filings=2)
        assert result.newly_captured == 1 and result.captured == 2
        assert len([url for url in calls if url.endswith("/current.htm")]) == 1
        await http.aclose()
    asyncio.run(run())


@pytest.mark.parametrize("invalid", ["contact", "universe", "budget"])
def test_operator_configuration_errors_fail_before_database_or_object_access(tmp_path, monkeypatch, invalid):
    import eventdesk.sec_collection as module
    monkeypatch.setenv("DATABASE_URL", "fixture-not-a-connection")
    monkeypatch.setenv("SEC_USER_AGENT", "" if invalid == "contact" else "EventDesk fixture@example.test")
    def forbidden(*args, **kwargs):
        raise AssertionError("Database must not be opened for invalid collector configuration")
    monkeypatch.setattr(module, "Store", forbidden)
    root = tmp_path/"must-not-exist"
    with pytest.raises(ValueError):
        asyncio.run(module.collect_configured(ciks=[] if invalid == "universe" else [CIK],
            objects_root=root, max_new_filings=0 if invalid == "budget" else 1))
    assert not root.exists()
