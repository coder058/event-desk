"""Transactional inbox, leased work queue, immutable prediction outbox."""
from __future__ import annotations

import hashlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import RLock
from typing import Any

from sqlalchemy import JSON, Float, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from eventdesk.config import PREDICTION_BUDGET_SECONDS, SUBMISSION_RESERVE_SECONDS
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
    local_trace: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    configuration_hash: Mapped[str | None] = mapped_column(String, nullable=True)


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (UniqueConstraint("slot", "webhook_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[str] = mapped_column(String)
    webhook_id: Mapped[str] = mapped_column(String)
    body_hash: Mapped[str] = mapped_column(String)
    event_id: Mapped[str] = mapped_column(String)
    received_at: Mapped[float] = mapped_column(Float)


class ServicePulse(Base):
    __tablename__ = "service_pulses"
    name: Mapped[str] = mapped_column(String, primary_key=True)
    seen_at: Mapped[float] = mapped_column(Float)
    details: Mapped[dict[str, Any]] = mapped_column(JSON)


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

    @contextmanager
    def fixture_guard(self) -> Iterator[None]:
        if self.engine.dialect.name == "sqlite":
            with self._fixture_lock:
                yield
        else:
            yield

    def initialize_fixture(self) -> None:
        """Only fixture/test startup; production schemas are migrated by Alembic."""
        Base.metadata.create_all(self.engine)

    def receive(self, slot: str, webhook_id: str, raw: bytes, event: Event, now: float) -> bool:
        digest = hashlib.sha256(raw).hexdigest()
        with self.fixture_guard(), Session(self.engine) as session, session.begin():
            # Serialize only this event/delivery identity, not every distinct event in one submission.
            if self.engine.dialect.name == "postgresql":
                from sqlalchemy import text
                # SOURCE: PostgreSQL advisory keys are signed 64-bit integers (eight bytes).
                # Ordered acquisition prevents deadlocks, including a hash collision across namespaces.
                names = ("receipt-event:" + slot + ":" + event.event_id,
                         "receipt-delivery:" + slot + ":" + webhook_id)
                keys = sorted({int.from_bytes(hashlib.sha256(name.encode()).digest()[:8], signed=True)
                               for name in names})
                for key in keys:
                    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
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
        with self.fixture_guard(), Session(self.engine) as session, session.begin():
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
                           analysis_trace: dict[str, Any] | None = None, defer_shadow: bool = False,
                           local_trace: dict[str, Any] | None = None, configuration_hash: str | None = None) -> None:
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
            job.local_trace = local_trace
            job.configuration_hash = configuration_hash

    def claim_shadow(self, now: float) -> ShadowWork | None:
        """Optional AI evidence cannot occupy prediction workers or run before acceptance."""
        with self.fixture_guard(), Session(self.engine) as session, session.begin():
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
            pulse = session.get(ServicePulse, "worker")
            now = time.time()
            # GUESS: three missed ten-second pulses signal degraded worker health; no market calibration.
            worker_fresh = pulse is not None and now - pulse.seen_at <= 30
            oldest = session.scalar(select(func.min(Job.deadline)).where(Job.state.in_(["pending", "working"])))
            return {"states": counts, "test_events": tests, "database": "reachable",
                    "worker": {"state": "recent_heartbeat" if worker_fresh else "unverified_or_stale",
                        "seen_at": pulse.seen_at if pulse else None, "details": pulse.details if pulse else None},
                    "deadline_at_risk": oldest is not None and oldest - now <= SUBMISSION_RESERVE_SECONDS}

    def pulse(self, name: str, details: dict[str, Any], now: float) -> None:
        with Session(self.engine) as session, session.begin():
            row = session.get(ServicePulse, name)
            if row is None:
                session.add(ServicePulse(name=name, seen_at=now, details=details))
            else:
                row.seen_at, row.details = now, details

    def scoreboard(self) -> dict[str, Any]:
        """Receipt coverage is a different denominator from official calendar eligibility."""
        with Session(self.engine) as session:
            base = select(func.count()).select_from(Job).where(Job.event_type != "TEST")
            received = int(session.scalar(base) or 0)
            accepted = int(session.scalar(base.where(Job.state == "api_accepted")) or 0)
            simulated = int(session.scalar(base.where(Job.state == "simulated")) or 0)
            material_fallbacks = int(session.scalar(base.where(Job.fallback.in_([
                "materials_missing_url", "materials_unavailable", "official_facts_missing",
                "invalid_materials_or_model_output"]))) or 0)
            latencies = list(session.scalars(select(Job.latency_ms).where(Job.event_type != "TEST",
                Job.state == "api_accepted", Job.latency_ms.is_not(None)).order_by(Job.latency_ms)).all())
            # SOURCE: empirical nearest-rank 95th percentile of observed receipt-to-API-response durations.
            import math
            p95 = latencies[math.ceil(.95 * len(latencies)) - 1] if latencies else None
            return {"received_submission_events": received, "api_accepted": accepted,
                "simulated": simulated, "material_fallbacks": material_fallbacks,
                "api_acceptance_fraction": accepted / received if received else None,
                "receipt_to_response_p95_ms": p95, "official_calendar_coverage": None,
                "official_live_score": None,
                "limits": "Received submission-events exclude TEST; multiple slots count separately. "
                          "API acceptance is not verified score eligibility; official calendar denominator is unavailable."}

    def public_predictions(self) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            # GUESS: bounded public response of the latest 100 entries; operational pagination, not trading calibration.
            jobs = session.scalars(select(Job).order_by(Job.id.desc()).limit(100)).all()
            return [{"event_id": j.event_id, "event_type": j.event_type, "slot": j.slot,
                     "received_at": j.received_at, "deadline": j.deadline, "state": j.state,
                     "predictions": j.payload["predictions"] if j.payload else None,
                     "model_hash": j.model_hash, "inputs_hash": j.inputs_hash,
                     "configuration_hash": j.configuration_hash,
                     "provider": j.provider, "fallback": j.fallback, "latency_ms": j.latency_ms,
                     "shadow_state": j.shadow_state,
                     "error": j.error, "submission_status": j.response.get("status") if j.response else None}
                    for j in jobs]

    def public_event(self, event_id: str, slot: str = "s1") -> dict[str, Any] | None:
        with Session(self.engine) as session:
            job = session.scalar(select(Job).where(Job.event_id == event_id, Job.slot == slot))
            if not job:
                return None
            return {"event_id": job.event_id, "slot": job.slot, "event_type": job.event_type,
                    "knowledge_cutoff": job.event.get("knowledge_cutoff"),
                    "official_items": job.inputs, "prediction": job.payload,
                    "inputs_hash": job.inputs_hash, "model_hash": job.model_hash,
                    "configuration_hash": job.configuration_hash,
                    "provider": job.provider, "fallback": job.fallback, "analysis_trace": job.analysis_trace,
                    "local_trace": job.local_trace,
                    "shadow_state": job.shadow_state,
                    "received_at": job.received_at, "deadline": job.deadline,
                    "submitted_at": job.submitted_at, "latency_ms": job.latency_ms,
                    "submission_response": job.response,
                    "state": job.state, "error": job.error}
