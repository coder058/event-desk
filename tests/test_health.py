from eventdesk.schemas import Event


def test_database_health_does_not_imply_worker_or_official_coverage(store, monkeypatch):
    import eventdesk.store as module
    monkeypatch.setattr(module.time, "time", lambda: 1000)
    assert store.health()["database"] == "reachable"
    assert store.health()["worker"]["state"] == "unverified_or_stale"
    store.pulse("worker", {"model_hash": "fixture", "llm_enabled": False}, 990)
    assert store.health()["worker"]["state"] == "recent_heartbeat"
    monkeypatch.setattr(module.time, "time", lambda: 1040)
    assert store.health()["worker"]["state"] == "unverified_or_stale"


def test_pending_prediction_alert_uses_actual_remaining_submission_reserve(store, monkeypatch):
    import eventdesk.store as module
    event = Event(id="delivery-deadline", event_id="event-deadline", event_type="TEST",
        focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    store.receive("s1", event.id, event.model_dump_json().encode(), event, 1000)
    monkeypatch.setattr(module.time, "time", lambda: 1200)
    assert store.health()["deadline_at_risk"] is False
    monkeypatch.setattr(module.time, "time", lambda: 1271)
    assert store.health()["deadline_at_risk"] is True
