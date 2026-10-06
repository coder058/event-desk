"""Read existing competition calendar/health; never trigger delivery or prediction."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import httpx

from eventdesk.config import COMPETITION_ORIGIN


def main() -> None:
    values = {}
    for line in (Path.home()/".eventdesk/.env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip('"').strip("'")
    # GUESS: bounded diagnostic request; not a measured competition latency guarantee.
    # UNCALIBRATED GUESS
    with httpx.Client(base_url=COMPETITION_ORIGIN, headers={"X-API-Key": values["EM_API_KEY"]},
                      timeout=15, follow_redirects=False) as client:
        records = {}
        for route in ("events", "health"):
            response = client.get("/"+route)
            if response.status_code != 200:
                raise RuntimeError("Read-only competition diagnostic failed: "+str(response.status_code))
            records[route] = response.json()
    private = Path("private/competition-state.json")
    private.parent.mkdir(exist_ok=True)
    private.write_text(json.dumps(records), encoding="utf-8")
    events = records["events"]
    health = records["health"]
    # Emit field names/aggregate counts only, never unknown fields or submission identifiers.
    print(json.dumps({"events": len(events), "event_field_names": sorted({key for e in events for key in e}),
        "event_types": dict(Counter(e.get("event_type") for e in events)),
        "timing_categories": dict(Counter(e.get("timing_category") for e in events)),
        "health_field_names": sorted(health),
        "health_numeric_counters": {key: value for key, value in health.items()
                                    if key.startswith(("webhook_n_", "submission_n_"))
                                    and isinstance(value, int) and not isinstance(value, bool)}}))


if __name__ == "__main__":
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    main()
