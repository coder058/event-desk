"""Retain the stopped local research budget once, without reading credential files."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from eventdesk.quota_transfer import CooldownRecord, QuotaSnapshot, UsageRecord


def main() -> None:
    source = Path("private/provider-probe.sqlite").resolve()
    target = Path("private/quota-source-sealed.json")
    if target.exists():
        snapshot = QuotaSnapshot.model_validate_json(target.read_bytes())
    else:
        # SOURCE: this fixed identity names the original, now-stopped local collector ledger.
        # Callers must stop all old collector processes before running this one-time command.
        with sqlite3.connect("file:"+source.as_posix()+"?mode=ro", uri=True) as database:
            database.row_factory = sqlite3.Row
            database.execute("BEGIN")
            usage = tuple(UsageRecord(**dict(row)) for row in database.execute(
                "SELECT id AS source_id,provider,created_at,reserved_tokens,actual_tokens "
                "FROM provider_usage ORDER BY id"))
            cooldowns = tuple(CooldownRecord(**dict(row)) for row in database.execute(
                "SELECT provider,cooldown_until FROM provider_state ORDER BY provider"))
            snapshot = QuotaSnapshot(ledger_id="eventdesk-local-research-v1", captured_at=time.time(),
                                     usage=usage, cooldowns=cooldowns)
        with target.open("x", encoding="utf-8") as stream:
            stream.write(snapshot.model_dump_json()+"\n")
    print(json.dumps({"ledger_id": snapshot.ledger_id, "snapshot_sha256": snapshot.digest(),
        "usage_rows": len(snapshot.usage), "provider_names": sorted({row.provider for row in snapshot.usage}),
        "source_sealed": True, "external_requests": 0}))


if __name__ == "__main__":
    main()
