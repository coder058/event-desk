import time

from fastapi.testclient import TestClient

from eventdesk.api import create_app
from eventdesk.config import Settings, Submission
from eventdesk.schemas import Event


def test_multiple_submissions_keep_distinct_prediction_evidence(settings, store):
    event = Event(id="delivery-shared", event_id="event-shared", event_type="TEST",
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    submissions = {**settings.submissions, "s2": Submission("s2", "fixture-key-2", "fixture-secret-2")}
    configured = Settings(settings.database_url, settings.model_path, submissions, True, frozenset())
    for slot, value in (("s1", .2), ("s2", .8)):
        store.receive(slot, event.id, event.model_dump_json().encode(), event, time.time())
        work = store.claim(time.time())
        assert work.slot == slot
        payload = {"event_id": event.event_id, "predictions": [{"identifier_value": "FIXTURE",
                                                               "predicted_percentile": value}]}
        store.persist_prediction(work.id, payload, {}, "fixture-" + slot, "official_test_event")
        store.finish(work.id, {"status": "fixture"}, "simulated", time.time())
    client = TestClient(create_app(configured, store))
    first = client.get("/api/events/event-shared?slot=s1").json()
    second = client.get("/api/events/event-shared?slot=s2").json()
    assert first["prediction"]["predictions"][0]["predicted_percentile"] == .2
    assert second["prediction"]["predictions"][0]["predicted_percentile"] == .8
    assert first["model_hash"] != second["model_hash"]
    assert client.get("/api/events/event-shared?slot=s3").status_code == 404
