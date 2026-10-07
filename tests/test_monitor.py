import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location("eventdesk_monitor", Path("ops/monitor.py"))
assert spec is not None and spec.loader is not None
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def test_monitor_distinguishes_worker_deadline_backup_and_https_conditions(tmp_path):
    now = datetime.now(UTC).timestamp()
    healthy = {"worker": {"state": "recent_heartbeat"}, "states": {}, "deadline_at_risk": False}
    backup = {"created_at": datetime.fromtimestamp(now, UTC).isoformat(), "remote_receipt_verified": True}
    assert monitor.evaluate(healthy, backup, now, True) == []
    unhealthy = {"worker": {"state": "unverified_or_stale"}, "states": {"expired": 1}, "deadline_at_risk": True}
    assert monitor.evaluate(unhealthy, None, now, False) == ["backup_transfer_unverified",
        "expired_or_rejected_predictions", "https_path_unverified", "submission_deadline_at_risk",
        "worker_heartbeat_unverified"]
    assert monitor.evaluate(healthy, backup, now+monitor.BACKUP_MAX_AGE_SECONDS+1, True) == ["backup_age_outside_guard"]
    record = tmp_path / "monitor" / "state.json"
    monitor.atomic_record(record, {"active_alerts": ["https_path_unverified"]})
    assert json.loads(record.read_text())["active_alerts"] == ["https_path_unverified"]
    assert not list(record.parent.glob(".monitor-*"))


def test_official_snapshot_failure_and_staleness_do_not_become_coverage():
    # PLACEHOLDER: synthetic times/counters exercise observability, not actual delivery.
    now = 10000
    assert monitor.evaluate_official(None, now) == ["official_observations_unverified"]
    record = {"observed_at": now, "collector": {"state": "observed"},
              "official_rolling_24h_counters": {"submission_n_total": 2}}
    official = {"configured_slots": ["s1"], "submissions": {"s1": record}}
    assert monitor.evaluate_official(official, now) == []
    record["collector"]["state"] = "observation_failed"
    assert monitor.evaluate_official(official, now) == ["official_observation_failed"]
    record["official_rolling_24h_counters"]["submission_n_late"] = 1
    assert monitor.evaluate_official(official, now+1201) == ["official_delivery_or_submission_failures",
        "official_observation_failed", "official_observations_stale"]
    official["configured_slots"].append("s2")
    assert "official_observations_unverified" in monitor.evaluate_official(official, now)
    record["collector"] = None
    assert "official_observation_failed" in monitor.evaluate_official(official, now)


def test_restore_proof_cannot_verify_a_later_or_different_backup():
    # PLACEHOLDER: synthetic immutable artifact identities and UTC timestamps.
    backup = {"created_at": "2026-10-07T04:00:00+00:00", "file": "fixture.age",
              "ciphertext_sha256": "fixture-ciphertext", "model_sha256": "fixture-model"}
    proof = {**backup, "restore_verified": True, "verified_at": "2026-10-07T05:00:00+00:00"}
    now = datetime(2026, 10, 7, 6, tzinfo=UTC).timestamp()
    assert monitor.verified_restore(backup, proof, now)
    assert not monitor.verified_restore({**backup, "file": "later.age"}, proof, now)
    assert not monitor.verified_restore({**backup, "ciphertext_sha256": "different"}, proof, now)
    assert not monitor.verified_restore(backup, {**proof, "verified_at": "2026-10-07T07:00:00+00:00"}, now)
    assert not monitor.verified_restore(backup, {**proof, "verified_at": "2026-10-07T05:00:00"}, now)
    assert not monitor.verified_restore(backup, None, now)
