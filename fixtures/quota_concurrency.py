"""Shared PostgreSQL research-import/admission races, with no provider requests."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eventdesk.quota_transfer import CooldownRecord, QuotaSnapshot, UsageRecord, import_ledger
from eventdesk.quotas import Limits, ProviderUsage, Quotas
from eventdesk.store import Store


def main() -> None:
    if os.getenv("EVENTDESK_FIXTURE_MODE", "false").lower() != "true":
        raise RuntimeError("Refusing synthetic quota imports against production")
    store = Store(os.environ["DATABASE_URL"])
    if store.engine.dialect.name != "postgresql":
        raise RuntimeError("Integration probe requires actual PostgreSQL")
    now = time.time()
    # PLACEHOLDER: synthetic 80-used/100-total token budget, not a provider entitlement.
    snapshot = QuotaSnapshot(ledger_id="fixture-quota-"+str(time.time_ns()), captured_at=now,
        usage=(UsageRecord(source_id=1, provider="groq", created_at=now, reserved_tokens=80),),
        cooldowns=(CooldownRecord(provider="groq", cooldown_until=0),))
    # GUESS: four duplicate attempts force lock contention; not a capacity claim. # UNCALIBRATED GUESS
    with ThreadPoolExecutor(max_workers=4) as pool:
        imported = list(pool.map(lambda _: import_ledger(store, snapshot, now), range(4)))
    assert imported.count(True) == 1
    with ThreadPoolExecutor(max_workers=4) as pool:
        accepted = list(pool.map(lambda _: Quotas(store).reserve("groq", 10, Limits(10, 10, 100, 100), now), range(4)))
    assert sum(usage is not None for usage in accepted) == 2
    with Session(store.engine) as session:
        assert session.scalar(select(func.count()).select_from(ProviderUsage).where(
            ProviderUsage.provider == "groq", ProviderUsage.created_at == now)) == 3
    print(json.dumps({"kind": "shared_postgresql_quota_fixture", "duplicate_import_attempts": len(imported),
        "committed_imports": 1, "accepted_runtime_reservations": 2, "external_requests": 0,
        "limits": "Synthetic project budget; not actual provider/account capacity"}))


if __name__ == "__main__":
    main()
