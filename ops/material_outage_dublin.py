"""Run the bounded mock-transport fault drill in a new disposable Dublin DB."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

REMOTE = '''
import json,subprocess,sys,time
data=json.load(sys.stdin);database='eventdesk_fault_'+str(time.time_ns())
db=['sudo','docker','exec','eventdesk-db-1']
subprocess.run(db+['createdb','-U','eventdesk',database],capture_output=True,check=True)
try:
 result=subprocess.run(['sudo','docker','exec','-i','eventdesk-worker-1','python','-c',data['script'],database,data['mode'],str(data['events'])],capture_output=True)
 print(result.stdout.decode().strip())
 if result.returncode: raise SystemExit(1)
finally:
 subprocess.run(db+['dropdb','-U','eventdesk',database],capture_output=True,check=True)
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("reserve", "source_outage"), required=True)
    parser.add_argument("--calendar-peak", action="store_true",
                        help="Use the peak from retained actual official observations, not an invented workload")
    args = parser.parse_args()
    # SOURCE: mission's baseline busy-day drill. Actual calendar workload has distinct provenance.
    events = 400
    provenance = {"source": "mission requested busy-day fixture", "events": events}
    if args.calendar_peak:
        import hashlib
        raw = Path("reports/dublin-official-observations.json").read_bytes()
        snapshot = Path("reports")/("workload-observation-"+hashlib.sha256(raw).hexdigest()+".json")
        if snapshot.exists():
            if snapshot.read_bytes() != raw:
                raise ValueError("Retained workload snapshot changed")
        else:
            with snapshot.open("xb") as stream:
                stream.write(raw)
        observations = json.loads(raw)["official_observations"]["submissions"]
        peaks = [(data["calendar"]["peak_scoring_window_entries"], slot, data)
                 for slot, data in observations.items()]
        events, slot, observation = max(peaks, key=lambda row: row[0])
        provenance = {"source": "retained official calendar, mutable schedule not simultaneous broadcasts",
            "report_sha256": hashlib.sha256(raw).hexdigest(), "snapshot": str(snapshot), "slot": slot,
            "observed_at": observation["observed_at"],
            "calendar_sha256": observation["calendar_sha256"],
            "day_central": observation["calendar"]["peak_scoring_window_day_central"], "events": events}
    if not isinstance(events, int) or isinstance(events, bool) or not 1 <= events <= 1000:
        # GUESS: same 1,000-event operational ceiling as the child fixture. # UNCALIBRATED GUESS
        raise ValueError("Unusable calendar workload")
    output = Path(f"reports/dublin-material-{args.mode}-{events}.json")
    if output.exists():
        raise RuntimeError("Refusing to overwrite a retained fault-drill report")
    data = {"script": Path("fixtures/material_outage.py").read_text(encoding="utf-8"), "mode": args.mode, "events": events}
    result = subprocess.run(SSH+["python3 -c "+shlex.quote(REMOTE)], input=json.dumps(data).encode(),
                            capture_output=True)
    if not result.stdout:
        raise RuntimeError("Fault drill or cleanup failed before a safe report was available")
    report = json.loads(result.stdout)
    report["workload_provenance"] = provenance
    output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report))
    if result.returncode:
        raise RuntimeError("Fault drill or cleanup failed; safe report retained, production was not a drill target")
