from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eventdesk.quota_transfer import QuotaImport, QuotaSnapshot, import_ledger, snapshot_ledger
from eventdesk.quotas import Limits, ProviderUsage, Quotas
from eventdesk.store import Store


def prepared_snapshot(store):
    # PLACEHOLDER: synthetic small quotas/times expose admission and conservative unsettled accounting.
    quotas = Quotas(store)
    limits = Limits(10, 10, 100, 100)
    first = quotas.reserve("groq", 40, limits, 1000)
    quotas.settle(first, 20, "validated", now=1000)
    quotas.reserve("groq", 60, limits, 1000)
    return snapshot_ledger(store, "fixture-stopped-research", 1001)


def destination(tmp_path):
    store = Store("sqlite:///"+str(tmp_path/"destination.sqlite"))
    store.initialize_fixture()
    return store


def test_import_charges_pending_usage_idempotently_and_survives_restart(store, tmp_path):
    snapshot = prepared_snapshot(store)
    target = destination(tmp_path)
    assert import_ledger(target, snapshot, 1001)
    assert not import_ledger(target, snapshot, 1001)
    with Session(target.engine) as session:
        assert session.scalar(select(func.count()).select_from(ProviderUsage)) == 2
        assert session.get(QuotaImport, snapshot.ledger_id).snapshot_sha256 == snapshot.digest()
    assert Quotas(Store(str(target.engine.url))).reserve("groq", 21, Limits(10, 10, 100, 100), 1001) is None
    assert Quotas(target).reserve("groq", 20, Limits(10, 10, 100, 100), 1001) is not None


def test_import_rejects_mutated_or_overlapping_source_without_charging_twice(store, tmp_path):
    snapshot = prepared_snapshot(store)
    target = destination(tmp_path)
    assert import_ledger(target, snapshot, 1001)
    altered = snapshot.model_copy(update={"captured_at": 1002.0})
    with pytest.raises(ValueError, match="changed"):
        import_ledger(target, altered, 1002)
    with Session(target.engine) as session:
        assert session.scalar(select(func.count()).select_from(ProviderUsage)) == 2


def test_cooldown_never_shortened_by_import(store, tmp_path):
    snapshot = prepared_snapshot(store)
    quotas = Quotas(store)
    quotas.settle(1, 20, "http_429", cooldown_seconds=100, now=1000)
    snapshot = snapshot_ledger(store, snapshot.ledger_id, 1001)
    target = destination(tmp_path)
    current = Quotas(target)
    usage = current.reserve("groq", 1, Limits(10, 10, 100, 100), 1000)
    current.settle(usage, 1, "http_429", cooldown_seconds=200, now=1000)
    import_ledger(target, snapshot, 1001)
    assert current.summary()["groq"]["cooldown_until"] == 1200


def test_snapshot_validation_rejects_ambiguous_counters_and_future_usage(store):
    snapshot = prepared_snapshot(store)
    for update in ({"reserved_tokens": True}, {"created_at": float("nan")},
                   {"created_at": 1002.0}, {"provider": "unknown"}, {"actual_tokens": -1}):
        data = snapshot.model_dump(mode="json")
        data["usage"][0].update(update)
        with pytest.raises(ValidationError):
            QuotaSnapshot.model_validate_json(__import__("json").dumps(data))


def test_identical_concurrent_imports_commit_once(store, tmp_path):
    snapshot = prepared_snapshot(store)
    target = destination(tmp_path)
    # PLACEHOLDER: four duplicate attempts test source identity, not load capacity.
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: import_ledger(target, snapshot, 1001), range(4)))
    assert results.count(True) == 1
