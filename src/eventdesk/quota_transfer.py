"""One-time, atomic transfer of a stopped research ledger into the shared budget.

The source must be sealed: a changed snapshot for the same identity is rejected.
Only usage counts/times/cooldowns are transferred, never keys or provider bodies.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Float, Integer, String, select, text
from sqlalchemy.orm import Mapped, Session, mapped_column

from eventdesk.quotas import ProviderState, ProviderUsage
from eventdesk.store import Base, Store

ProviderName = Literal["gemini", "groq"]


def provider_name(value: str) -> ProviderName:
    if value == "gemini":
        return "gemini"
    if value == "groq":
        return "groq"
    raise ValueError("Unrecognized sealed-ledger provider")


class QuotaImport(Base):
    __tablename__ = "quota_imports"
    ledger_id: Mapped[str] = mapped_column(String, primary_key=True)
    snapshot_sha256: Mapped[str] = mapped_column(String)
    captured_at: Mapped[float] = mapped_column(Float)
    imported_at: Mapped[float] = mapped_column(Float)
    usage_rows: Mapped[int] = mapped_column(Integer)


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)
    source_id: int = Field(gt=0)
    provider: ProviderName
    created_at: float = Field(ge=0)
    reserved_tokens: int = Field(ge=0)
    actual_tokens: int | None = Field(default=None, ge=0)


class CooldownRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)
    provider: ProviderName
    cooldown_until: float = Field(ge=0)


class QuotaSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)
    ledger_id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    captured_at: float = Field(ge=0)
    usage: tuple[UsageRecord, ...]
    cooldowns: tuple[CooldownRecord, ...]

    @model_validator(mode="after")
    def validate_identity(self) -> QuotaSnapshot:
        if len({row.source_id for row in self.usage}) != len(self.usage):
            raise ValueError("Duplicate source usage identity")
        if len({row.provider for row in self.cooldowns}) != len(self.cooldowns):
            raise ValueError("Duplicate provider cooldown")
        if any(row.created_at > self.captured_at for row in self.usage):
            raise ValueError("Usage cannot follow snapshot capture")
        return self

    def digest(self) -> str:
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode()).hexdigest()


def snapshot_ledger(store: Store, ledger_id: str, now: float | None = None) -> QuotaSnapshot:
    """Read after stopping source writers; this function does not seal an active source."""
    captured_at = time.time() if now is None else now
    with store.fixture_guard(), Session(store.engine) as session, session.begin():
        usage = tuple(UsageRecord(source_id=row.id, provider=provider_name(row.provider),
            created_at=row.created_at, reserved_tokens=row.reserved_tokens, actual_tokens=row.actual_tokens)
            for row in session.scalars(select(ProviderUsage).order_by(ProviderUsage.id)))
        cooldowns = tuple(CooldownRecord(provider=provider_name(row.provider), cooldown_until=row.cooldown_until)
            for row in session.scalars(select(ProviderState).order_by(ProviderState.provider)))
    return QuotaSnapshot(ledger_id=ledger_id, captured_at=captured_at, usage=usage, cooldowns=cooldowns)


def import_ledger(store: Store, snapshot: QuotaSnapshot, now: float | None = None) -> bool:
    """Returns False for an identical retry; rejects a changed source atomically."""
    imported_at = time.time() if now is None else now
    if not math.isfinite(imported_at) or imported_at < snapshot.captured_at:
        raise ValueError("Invalid import timestamp")
    digest = snapshot.digest()
    providers = sorted({row.provider for row in snapshot.usage} | {row.provider for row in snapshot.cooldowns})
    with store.fixture_guard(), Session(store.engine) as session, session.begin():
        if store.engine.dialect.name == "postgresql":
            # SOURCE: same provider-budget lock as runtime admission/settlement; all providers ordered.
            for provider in providers:
                session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:provider))"),
                                {"provider": "provider-budget:"+provider})
            session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:ledger))"),
                            {"ledger": "quota-import:"+snapshot.ledger_id})
        previous = session.get(QuotaImport, snapshot.ledger_id, with_for_update=True)
        if previous is not None:
            if previous.snapshot_sha256 != digest:
                raise ValueError("Sealed research ledger changed; refusing overlapping import")
            return False
        for provider in providers:
            state = session.get(ProviderState, provider, with_for_update=True)
            if state is None:
                state = ProviderState(provider=provider, cooldown_until=0)
                session.add(state)
                session.flush()
            cooldown = next((row.cooldown_until for row in snapshot.cooldowns if row.provider == provider), 0)
            state.cooldown_until = max(state.cooldown_until, cooldown)
        for row in snapshot.usage:
            session.add(ProviderUsage(provider=row.provider, created_at=row.created_at,
                reserved_tokens=row.reserved_tokens, actual_tokens=row.actual_tokens, status="sealed_research_import"))
        session.add(QuotaImport(ledger_id=snapshot.ledger_id, snapshot_sha256=digest,
            captured_at=snapshot.captured_at, imported_at=imported_at, usage_rows=len(snapshot.usage)))
    return True
