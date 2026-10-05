"""Shared durable provider admission control. Conservative reservation before external calls."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Float, Integer, String, func, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from eventdesk.store import Base, Store


class ProviderState(Base):
    __tablename__ = "provider_state"
    provider: Mapped[str] = mapped_column(String, primary_key=True)
    cooldown_until: Mapped[float] = mapped_column(Float, default=0)
    last_status: Mapped[str | None] = mapped_column(String, nullable=True)


class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[float] = mapped_column(Float)
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    actual_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String)


@dataclass(frozen=True)
class Limits:
    requests_minute: int
    requests_day: int
    tokens_minute: int
    tokens_day: int


class Quotas:
    def __init__(self, store: Store) -> None:
        self.store = store

    def reserve(self, provider: str, tokens: int, limits: Limits, now: float) -> int | None:
        with self.store._fixture_lock, Session(self.store.engine) as session, session.begin():
            if self.store.engine.dialect.name == "postgresql":
                session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:provider))"),
                                {"provider": "provider-budget:" + provider})
            state = session.get(ProviderState, provider, with_for_update=True)
            if state is None:
                state = ProviderState(provider=provider, cooldown_until=0)
                session.add(state)
                session.flush()
            if state.cooldown_until > now:
                return None
            # SOURCE: minute/day units; rolling day is deliberately stricter than calendar quota resets.
            minute, day = now - 60, now - 86400
            counts: dict[str, tuple[int, int]] = {}
            for label, since in (("minute", minute), ("day", day)):
                row = session.execute(select(func.count(), func.coalesce(func.sum(func.coalesce(
                    ProviderUsage.actual_tokens, ProviderUsage.reserved_tokens)), 0)).where(
                    ProviderUsage.provider == provider, ProviderUsage.created_at > since)).one()
                counts[label] = int(row[0]), int(row[1])
            if (counts["minute"][0] >= limits.requests_minute or counts["day"][0] >= limits.requests_day
                    or counts["minute"][1] + tokens > limits.tokens_minute
                    or counts["day"][1] + tokens > limits.tokens_day):
                return None
            usage = ProviderUsage(provider=provider, created_at=now, reserved_tokens=tokens,
                                  actual_tokens=None, status="reserved")
            session.add(usage)
            session.flush()
            return usage.id

    def settle(self, usage_id: int, actual_tokens: int | None, status: str,
               cooldown_seconds: float = 0, now: float | None = None) -> None:
        current = time.time() if now is None else now
        with Session(self.store.engine) as session, session.begin():
            usage = session.get(ProviderUsage, usage_id, with_for_update=True)
            if usage is None:
                raise RuntimeError("Missing quota reservation")
            usage.actual_tokens = actual_tokens
            usage.status = status
            state = session.get(ProviderState, usage.provider, with_for_update=True)
            if state is None:
                raise RuntimeError("Missing provider state")
            state.last_status = status
            state.cooldown_until = max(state.cooldown_until, current + cooldown_seconds)

    def summary(self) -> dict[str, Any]:
        with Session(self.store.engine) as session:
            return {state.provider: {"cooldown_until": state.cooldown_until, "last_status": state.last_status}
                    for state in session.scalars(select(ProviderState))}
