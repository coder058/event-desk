import time

from sqlalchemy.orm import Session

from eventdesk.schemas import Event
from eventdesk.store import Job


def test_expired_backlog_cannot_hide_the_next_valid_prediction(store):
    now = time.time()
    event = Event(id="valid", event_id="valid", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    # SOURCE: mission's 400-event busy-day count; synthetic expired work, not market observations.
    with Session(store.engine) as session, session.begin():
        session.add_all(Job(slot="s1", event_id=f"expired-{i}", event_type="TEST",
            event=event.model_dump(mode="json"), received_at=now-300, deadline=now,
            state="pending", lease_until=0) for i in range(400))
    store.receive("s1", event.id, event.model_dump_json().encode(), event, now)
    work = store.claim(now)
    assert work is not None and work.event.event_id == "valid"
    assert store.health()["states"] == {"expired": 400, "working": 1}


def test_expired_optional_evidence_cannot_hide_valid_shadow_work(store):
    now = time.time()
    event = Event(id="valid-shadow", event_id="valid-shadow", event_type="TEST",
                  focal_assets=[{"identifier_type": "TICKER", "identifier_value": "FIXTURE"}])
    payload = {"event_id": event.event_id, "predictions": [{"predicted_percentile": .5}]}
    # PLACEHOLDER: synthetic mathematical payload and 400 stale optional jobs; no AI finding.
    with Session(store.engine) as session, session.begin():
        session.add_all(Job(slot="s1", event_id=f"expired-shadow-{i}", event_type="TEST",
            event=event.model_dump(mode="json"), received_at=now-300, deadline=now,
            state="api_accepted", shadow_state="pending", shadow_lease_until=0) for i in range(400))
        session.add(Job(slot="s1", event_id=event.event_id, event_type="TEST",
            event=event.model_dump(mode="json"), received_at=now, deadline=now+300,
            state="api_accepted", shadow_state="pending", shadow_lease_until=0,
            inputs={"earnings-call-facts": ["fixture"]}, payload=payload))
    work = store.claim_shadow(now)
    assert work is not None and work.event_id == event.event_id
    with Session(store.engine) as session:
        assert all(job.shadow_state == "expired" for job in session.query(Job).filter(Job.event_id != event.event_id))
