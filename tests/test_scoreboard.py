import time

from fastapi.testclient import TestClient

from eventdesk.api import create_app
from eventdesk.schemas import Event


def test_scoreboard_does_not_confuse_test_fixture_and_eligible_live_events(settings, store):
    client = TestClient(create_app(settings, store))
    empty = client.get("/api/scoreboard").json()
    assert empty["api_acceptance_fraction"] is None
    assert empty["official_calendar_coverage"] is None
    for identity, kind, state, fallback in (("test", "TEST", "api_accepted", "official_test_event"),
            ("simulation", "EARNINGS", "simulated", "llm_not_enabled"),
            ("received", "EARNINGS", "api_accepted", "materials_unavailable")):
        event = Event(id=identity, event_id=identity, event_type=kind,
                      focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
        now = time.time()
        store.receive("s1", identity, event.model_dump_json().encode(), event, now)
        work = store.claim(now)
        store.persist_prediction(work.id, {"event_id": identity, "predictions": []}, {}, "fixture", fallback)
        store.finish(work.id, {"status": "test"}, state, now + 1)
    result = client.get("/api/scoreboard").json()
    assert result["received_submission_events"] == 2
    assert result["api_accepted"] == 1
    assert result["api_acceptance_fraction"] == .5
    assert result["simulated"] == 1
    assert result["material_fallbacks"] == 1
    assert result["receipt_to_response_p95_ms"] == 1000
    assert result["official_live_score"] is None
