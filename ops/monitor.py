"""Host-side health/backup monitoring; independent of the deadline-critical worker."""
# SOURCE: Dublin host Python 3.10 compatibility; application containers use Python 3.12.
# ruff: noqa: UP017
from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ORIGIN = "http://127.0.0.1:8800"
PUBLIC = "https://52.17.192.36.sslip.io"
# GUESS: three-second operational probe and twenty-six-hour backup age allowance.
# UNCALIBRATED GUESS: these alert thresholds need observed operational behavior.
PROBE_SECONDS = 3
BACKUP_MAX_AGE_SECONDS = 26 * 3600


def read_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=PROBE_SECONDS) as response:
        # GUESS: 1 MiB maximum for bounded metadata probes, not source material.
        # UNCALIBRATED GUESS
        raw = response.read(1024*1024+1)
    if len(raw) > 1024*1024:
        raise ValueError("Operational metadata too large")
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError("Invalid operational response")
    return result


def evaluate(health: dict | None, backup: dict | None, now: float, https_verified: bool) -> list[str]:
    alerts = []
    if health is None:
        alerts.append("origin_unreachable")
    else:
        if health.get("worker", {}).get("state") != "recent_heartbeat":
            alerts.append("worker_heartbeat_unverified")
        if health.get("deadline_at_risk") is True:
            alerts.append("submission_deadline_at_risk")
        states = health.get("states", {})
        if states.get("expired", 0) or states.get("rejected", 0):
            alerts.append("expired_or_rejected_predictions")
    if not https_verified:
        alerts.append("https_path_unverified")
    if backup is None or backup.get("remote_receipt_verified") is not True:
        alerts.append("backup_transfer_unverified")
    else:
        try:
            created = datetime.fromisoformat(backup["created_at"])
            if created.tzinfo is None:
                raise ValueError("Naive backup timestamp")
            age = now-created.timestamp()
            if age < 0 or age > BACKUP_MAX_AGE_SECONDS:
                alerts.append("backup_age_outside_guard")
        except (KeyError, TypeError, ValueError):
            alerts.append("backup_timestamp_invalid")
    return sorted(alerts)


def atomic_record(path: Path, record: dict) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".monitor-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(record, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def telegram(message: str) -> str:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN", ""), os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return "local_only_optional_credentials_absent"
    payload = json.dumps({"chat_id": chat, "text": message}).encode()
    request = urllib.request.Request("https://api.telegram.org/bot"+token+"/sendMessage", data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        # GUESS: bounded optional notification; never a submission worker dependency.
        # UNCALIBRATED GUESS
        with urllib.request.urlopen(request, timeout=5) as response:
            if response.status != 200:
                return "notification_unverified"
        return "notification_api_accepted"
    except (OSError, urllib.error.URLError):
        # Do not print request URLs or exception text: the URL contains the Telegram token.
        return "notification_unavailable"


def run() -> None:
    os.umask(0o077)
    path = Path("/var/lib/eventdesk/monitor/state.json")
    previous = json.loads(path.read_text()) if path.is_file() else {}
    now = time.time()
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    health, scoreboard, backup = None, None, None
    try:
        health = read_json(ORIGIN+"/healthz")
        scoreboard = read_json(ORIGIN+"/api/scoreboard")
    except (OSError, ValueError, urllib.error.URLError):
        pass
    try:
        backup = json.loads(Path("/var/lib/eventdesk/backups/latest.json").read_text())
    except (OSError, ValueError):
        pass
    try:
        public = read_json(PUBLIC+"/healthz")
        origin_https_verified = public.get("database") == "reachable" and public.get("fixture_mode") is False
    except (OSError, ValueError, urllib.error.URLError):
        origin_https_verified = False
    # A successful self-request does not traverse or verify the public inbound firewall.
    try:
        proof = json.loads(path.with_name("external-https.json").read_text())
        external_https_verified = proof.get("verified") is True and proof.get("origin") == PUBLIC
    except (OSError, ValueError):
        external_https_verified = False
    alerts = evaluate(health, backup, now, origin_https_verified and external_https_verified)
    old = set(previous.get("active_alerts", []))
    new, resolved = sorted(set(alerts)-old), sorted(old-set(alerts))
    if new or resolved:
        transition = {"kind": "ops_alert_transition", "at": now, "new": new, "resolved": resolved}
        transition["notification"] = telegram("Event Desk alerts: new="+",".join(new)+"; resolved="+",".join(resolved))
        print(json.dumps(transition), flush=True)
    if previous.get("summary_day") != day:
        summary = {"kind": "daily_operational_summary", "day_utc": day,
            "received_submission_events": scoreboard.get("received_submission_events") if scoreboard else None,
            "api_accepted": scoreboard.get("api_accepted") if scoreboard else None,
            "official_calendar_coverage": None, "active_alerts": alerts,
            "limits": "Cumulative received-event counts, not eligible daily coverage or a live score"}
        print(json.dumps(summary), flush=True)
        telegram("Event Desk daily status: "+json.dumps(summary, sort_keys=True))
    atomic_record(path, {"checked_at": now, "active_alerts": alerts, "summary_day": day,
        "https_origin_probe_verified": origin_https_verified,
        "https_external_probe_verified": external_https_verified,
        "limits": "An origin-side HTTPS probe cannot verify the Lightsail external inbound rule",
        "backup_transfer_at": backup.get("created_at") if backup else None,
        "backup_restore_verified": False})


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print(json.dumps({"monitor_failed": True, "error_type": type(exc).__name__}), flush=True)
        raise SystemExit(1) from None
