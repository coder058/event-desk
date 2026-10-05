"""Transactional inbox, leased work queue, immutable prediction outbox."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from threading import RLock
from typing import Any

from sqlalchemy import JSON, Float, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from eventdesk.config import PREDICTION_BUDGET_SECONDS
from eventdesk.schemas import Event


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("slot", "event_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String)
    event_id: Mapped[str] = mapped_column(String)
    event_type: Mapped[str] = mapped_column(String)
    event: Mapped[dict[str, Any]] = mapped_column(JSON)
    received_at: Mapped[float] = mapped_column(Float)
    deadline: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String, default="pending")
    lease_until: Mapped[float] = mapped_column(Float, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    inputs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    inputs_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    model_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    fallback: Mapped[str | None] = mapped_column(String, nullable=True)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_trace: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    shadow_state: Mapped[str | None] = mapped_column(String, nullable=True)
    shadow_lease_until: Mapped[float] = mapped_column(Float, default=0)


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("slot", "webhook_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String)
    webhook_id: Mapped[str] = mapped_column(String)
    body_hash: Mapped[str] = mapped_column(String)
    event_id: Mapped[str] = mapped_column(String)
    received_at: Mapped[float] = mapped_column(Float)


@dataclass(frozen=True)
class Work:
    id: int
    slot: str
    event: Event
    deadline: float
    received_at: float
    payload: dict[str, Any] | None


@dataclass(frozen=True)
class ShadowWork:
    id: int
    event_id: str
    items: dict[str, Any]
    deadline: float
    local_prediction: float


class ConflictError(Exception):
    pass


class Store:
    def __init__(self, url: str) -> None:
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine: Engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
        self._fixture_lock = RLock()

    def initialize_fixture(self) -> None:
        """Only fixture/test startup; production schemas are migrated by Alembic."""
        Base.metadata.create_all(self.engine)

    def receive(self, slot: str, webhook_id: str, raw: bytes, event: Event, now: float) -> bool:
        digest = hashlib.sha256(raw).hexdigest()
        with self._fixture_lock, Session(self.engine) as session, session.begin():
            # Serialize receipt per slot across processes without locking the whole inbox.
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy import text
                session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:slot))"), {"slot": slot})
            existing = session.scalar(select(Delivery).where(Delivery.slot == slot, Delivery.webhook_id == webhook_id))
            if existing:
                if existing.body_hash != digest:
                    raise ConflictError("Reused delivery identifier with different content")
                return False
            job = session.scalar(select(Job).where(Job.slot == slot, Job.event_id == event.event_id))
            if job and (job.event_type != event.event_type or job.event["focal_assets"] != event.model_dump(mode="json")["focal_assets"]):
                raise ConflictError("Changed event identity")
            if not job:
                deadline = now + PREDICTION_BUDGET_SECONDS
                if event.prediction_deadline is not None:
                    deadline = min(deadline, event.prediction_deadline.timestamp())
                session.add(Job(slot=slot, event_id=event.event_id, event_type=event.event_type,
                                event=event.model_dump(mode="json"), received_at=now, deadline=deadline,
                                state="pending", lease_until=0, attempts=0))
            session.add(Delivery(slot=slot, webhook_id=webhook_id, body_hash=digest,
                                 event_id=event.event_id, received_at=now))
            return job is None

    def claim(self, now: float) -> Work | None:
        with self._fixture_lock, Session(self.engine) as session, session.begin():
            query = (select(Job).where(Job.state.in_(["pending", "working"]), Job.lease_until <= now)
                     .order_by(Job.deadline, Job.id).limit(1).with_for_update(skip_locked=True))
            job = session.scalar(query)
            if job is None:
                return None
            if job.deadline <= now:
                job.state, job.error = "expired", "deadline_expired"
                return None
            job.state = "working"
            # SOURCE: hold the lease to this event's actual deadline; a crashed worker must be recovered
            # by startup release rather than an unsafe short lease that duplicates in-flight prediction work.
            job.lease_until = job.deadline
            job.attempts += 1
            return Work(job.id, job.slot, Event.model_validate(job.event), job.deadline,
                        job.received_at, job.payload)

    def recover(self) -> int:
        """Call only when the single worker service starts; release abandoned leases."""
        from sqlalchemy import update
        with Session(self.engine) as session, session.begin():
            result = session.execute(update(Job).where(Job.state == "working").values(lease_until=0))
            session.execute(update(Job).where(Job.shadow_state == "working").values(shadow_lease_until=0))
            return int(result.rowcount)  # type: ignore[attr-defined]

    def persist_prediction(self, job_id: int, payload: dict[str, Any], items: dict[str, Any],
                           model_hash: str, fallback: str | None, provider: str = "local",
                           analysis_trace: dict[str, Any] | None = None, defer_shadow: bool = False) -> None:
        from eventdesk.materials import input_hash
        with Session(self.engine) as session, session.begin():
            job = session.get(Job, job_id, with_for_update=True)
            if job is None:
                raise RuntimeError("Missing job")
            if job.payload is not None:
                if job.payload != payload:
                    raise ConflictError("Prediction outbox is immutable")
                return
            job.payload, job.inputs, job.inputs_hash = payload, items, input_hash(items)
            job.model_hash, job.fallback, job.provider = model_hash, fallback, provider
            # Outbox and analysis must commit together; a crash between separate commits loses coverage.
            job.analysis_trace = analysis_trace
            job.shadow_state = "pending" if defer_shadow else None

    def claim_shadow(self, now: float) -> ShadowWork | None:
        """Optional AI evidence cannot occupy prediction workers or run before acceptance."""
        with self._fixture_lock, Session(self.engine) as session, session.begin():
            job = session.scalar(select(Job).where(Job.state == "api_accepted",
                Job.shadow_state.in_(["pending", "working"]), Job.shadow_lease_until <= now)
                .order_by(Job.deadline, Job.id).limit(1).with_for_update(skip_locked=True))
            if job is None:
                return None
            if job.deadline <= now:
                job.shadow_state = "expired"
                return None
            if not job.inputs or not job.payload:
                job.shadow_state = "invalid"
                return None
            job.shadow_state, job.shadow_lease_until = "working", job.deadline
            return ShadowWork(job.id, job.event_id, job.inputs, job.deadline,
                              float(job.payload["predictions"][0]["predicted_percentile"]))

    def finish_shadow(self, job_id: int, trace: dict[str, Any], state: str) -> None:
        with Session(self.engine) as session, session.begin():
            job = session.get(Job, job_id, with_for_update=True)
            if job is None or job.state != "api_accepted" or job.provider != "local":
                raise ConflictError("Shadow evidence requires an accepted immutable local prediction")
            if trace.get("affects_prediction") is not False:
                raise ConflictError("Shadow evidence cannot change a prediction")
            # Evidence attaches to the retained input hash; payload/provider/submission timestamps stay immutable.
            job.analysis_trace, job.shadow_state = trace, state

    def finish(self, job_id: int, response: dict[str, Any], state: str, now: float) -> None:
        with Session(self.engine) as session, session.begin():
            job = session.get(Job, job_id, with_for_update=True)
            if job is None or job.payload is None:
                raise RuntimeError("Cannot finish without persisted prediction")
            job.state, job.response = state, response
            job.submitted_at, job.latency_ms = now, (now - job.received_at) * 1000

    def retry(self, job_id: int, reason: str, delay: float, now: float) -> None:
        with Session(self.engine) as session, session.begin():
            job = session.get(Job, job_id, with_for_update=True)
            if job is None:
                raise RuntimeError("Missing job")
            job.error = reason
            job.state = "pending" if now + delay < job.deadline else "expired"
            job.lease_until = now + delay

    def health(self) -> dict[str, Any]:
        with Session(self.engine) as session:
            counts: dict[str, int] = {row[0]: row[1] for row in
                                     session.execute(select(Job.state, func.count()).group_by(Job.state))}
            tests = session.scalar(select(func.count()).where(Job.event_type == "TEST"))
            return {"states": counts, "test_events": tests, "database": "reachable"}

    def public_predictions(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            # GUESS: bounded public response of the latest 100 entries; operational pagination, not trading calibration.
            jobs = session.scalars(select(Job).order_by(Job.id.desc()).limit(100)).all()
            return [{"event_id": j.event_id, "event_type": j.event_type, "slot": j.slot,
                     "received_at": j.received_at, "deadline": j.deadline, "state": j.state,
                     "predictions": j.payload["predictions"] if j.payload else None,
                     "model_hash": j.model_hash, "inputs_hash": j.inputs_hash,
                     "provider": j.provider, "fallback": j.fallback, "latency_ms": j.latency_ms,
                     "shadow_state": j.shadow_state,
                     "error": j.error, "submission_status": j.response.get("status") if j.response else None}
                    for j in jobs]

    def public_event(self, event_id: str) -> dict[str, Any] | None:
        with Session(self.engine) as session:
            job = session.scalar(select(Job).where(Job.event_id == event_id))
            if not job:
                return None
            return {"event_id": job.event_id, "event_type": job.event_type,
                    "knowledge_cutoff": job.event.get("knowledge_cutoff"),
                    "official_items": job.inputs, "prediction": job.payload,
                    "inputs_hash": job.inputs_hash, "model_hash": job.model_hash,
                    "provider": job.provider, "fallback": job.fallback, "analysis_trace": job.analysis_trace,
                    "shadow_state": job.shadow_state,
                    "state": job.state, "error": job.error}
