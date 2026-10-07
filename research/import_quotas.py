"""Import only a sealed usage snapshot; this command never calls an external API."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from eventdesk.quota_transfer import QuotaSnapshot, import_ledger
from eventdesk.store import Store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        raise RuntimeError("Quota migration requires shared PostgreSQL")
    snapshot = QuotaSnapshot.model_validate_json(args.snapshot.read_bytes())
    inserted = import_ledger(Store(url), snapshot)
    print(json.dumps({"ledger_id": snapshot.ledger_id, "snapshot_sha256": snapshot.digest(),
        "usage_rows": len(snapshot.usage), "inserted": inserted,
        "limits": "Project usage only; other account consumers and provider limits may differ"}))


if __name__ == "__main__":
    main()
