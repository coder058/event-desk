import asyncio
import gzip

import httpx
import pytest

from eventdesk.evidence import RawObjects
from eventdesk.sec_transport import SecFetchFailed, SecTransport


class FakeGate:
    def __init__(self):
        self.admitted = []
        self.finished = []

    def acquire(self, url):
        self.admitted.append(url)
        return self

    def finish(self, *result):
        self.finished.append(result)


def test_identification_required_before_any_read_or_admission(tmp_path):
    gate = FakeGate()
    with pytest.raises(ValueError, match="SEC_USER_AGENT"):
        SecTransport(contact="", gate=gate, objects=RawObjects(tmp_path))
    assert not gate.admitted


def test_gzip_entity_capture_is_hashed_once_without_contact_in_provenance(tmp_path):
    gate = FakeGate()
    raw = b'{"synthetic":true}'
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers["User-Agent"] == "EventDesk fixture@example.test"
        return httpx.Response(200, content=gzip.compress(raw), headers={"Content-Encoding": "gzip"})
    async def run():
        objects = RawObjects(tmp_path)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = SecTransport(contact="EventDesk fixture@example.test", gate=gate, objects=objects, http=http)
            document = await source.submissions("123")
        assert objects.read(document.content_sha256) == raw
        assert document.accepted_at is None
        assert "example.test" not in document.model_dump_json()
        assert gate.finished == [("captured", 200, len(raw), 0.0)]
    asyncio.run(run())
    assert str(requests[0].url) == "https://data.sec.gov/submissions/CIK0000000123.json"


@pytest.mark.parametrize("status", [302, 403, 429, 503])
def test_redirects_and_blocks_cannot_capture_error_pages_or_follow_another_host(tmp_path, status):
    gate = FakeGate()
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=b"synthetic blocked page", headers={
            "Location": "https://another.example/", "Retry-After": "600"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
            source = SecTransport(contact="EventDesk fixture@example.test", gate=gate, objects=RawObjects(tmp_path), http=http)
            with pytest.raises(SecFetchFailed, match="http_"+str(status)):
                await source.submissions("123")
    asyncio.run(run())
    assert len(calls) == 1
    assert gate.finished[-1] == ("http_"+str(status), status, None, 600.0 if status != 302 else 0.0)
    assert list(tmp_path.iterdir()) == []


def test_total_budget_and_cancellation_finish_the_admission_without_claiming_capture(tmp_path, monkeypatch):
    import eventdesk.sec_transport as module
    # PLACEHOLDER: short synthetic network budget, not actual observed SEC latency.
    monkeypatch.setattr(module, "HTTP_BUDGET_SECONDS", 0.02)
    gate = FakeGate()
    async def handler(request):
        await asyncio.Event().wait()
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = SecTransport(contact="EventDesk fixture@example.test", gate=gate, objects=RawObjects(tmp_path), http=http)
            with pytest.raises(SecFetchFailed, match="TimeoutError"):
                await source.submissions("123")
    asyncio.run(run())
    assert gate.finished[-1][0] == "transport_TimeoutError"
    assert list(tmp_path.iterdir()) == []


def test_task_cancellation_releases_admission_without_a_successful_capture(tmp_path):
    gate = FakeGate()
    async def run():
        started = asyncio.Event()
        async def handler(request):
            started.set()
            await asyncio.Event().wait()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            source = SecTransport(contact="EventDesk fixture@example.test", gate=gate, objects=RawObjects(tmp_path), http=http)
            task = asyncio.create_task(source.submissions("123"))
            await started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    asyncio.run(run())
    assert gate.finished[-1] == ("interrupted", None, None, 0.0)


def test_decoded_body_limit_stops_without_persisting_a_partial_source(tmp_path, monkeypatch):
    import eventdesk.sec_transport as module
    # PLACEHOLDER: synthetic four-byte limit exercises entity-body admission.
    monkeypatch.setattr(module, "MAX_SUBMISSIONS_BYTES", 4)
    gate = FakeGate()
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"12345"))) as http:
            source = SecTransport(contact="EventDesk fixture@example.test", gate=gate, objects=RawObjects(tmp_path), http=http)
            with pytest.raises(SecFetchFailed, match="body_too_large"):
                await source.submissions("123")
    asyncio.run(run())
    assert gate.finished[-1] == ("body_too_large", 200, None, 0.0)
    assert list(tmp_path.iterdir()) == []
