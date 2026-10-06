import json

import pytest

from eventdesk.telemetry import Telemetry


def test_actual_otel_spans_retain_correlation_without_source_text_urls_or_exception_messages(caplog):
    caplog.set_level("INFO", logger="eventdesk.telemetry")
    telemetry = Telemetry()
    try:
        with pytest.raises(ValueError):
            with telemetry.stage("eventdesk.job", **{"eventdesk.job_id": 1, "eventdesk.slot": "s1",
                    "eventdesk.model_sha256": "a"*64, "source_quote": "never-emit",
                    "http.url": "https://signed.invalid/?secret=never-emit"}):
                with telemetry.stage("eventdesk.local_inference"):
                    raise ValueError("never-emit signed credential")
    finally:
        telemetry.shutdown()
    records = [json.loads(record.message) for record in caplog.records if record.name == "eventdesk.telemetry"]
    assert len(records) == 2
    parent = next(record for record in records if record["stage"] == "eventdesk.job")
    child = next(record for record in records if record["stage"] == "eventdesk.local_inference")
    assert parent["trace_id"] == child["trace_id"]
    assert child["parent_span_id"] == parent["span_id"]
    assert parent["attributes"]["eventdesk.job_id"] == 1
    assert child["status"] == "ERROR"
    assert child["attributes"]["error.type"] == "ValueError"
    assert "never-emit" not in json.dumps(records)
