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
