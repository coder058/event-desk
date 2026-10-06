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
 result=subprocess.run(['sudo','docker','exec','-i','eventdesk-worker-1','python','-c',data['script'],database,data['mode']],capture_output=True)
 print(result.stdout.decode().strip())
 if result.returncode: raise SystemExit(1)
finally:
 subprocess.run(db+['dropdb','-U','eventdesk',database],capture_output=True,check=True)
'''


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("reserve", "source_outage"), required=True)
    args = parser.parse_args()
    data = {"script": Path("fixtures/material_outage.py").read_text(encoding="utf-8"), "mode": args.mode}
    result = subprocess.run(SSH+["python3 -c "+shlex.quote(REMOTE)], input=json.dumps(data).encode(),
                            capture_output=True)
    if not result.stdout:
        raise RuntimeError("Fault drill or cleanup failed before a safe report was available")
    report = json.loads(result.stdout)
    Path("reports/dublin-material-"+args.mode+".json").write_text(json.dumps(report, indent=2)+"\n",
                                                               encoding="utf-8")
    print(json.dumps(report))
    if result.returncode:
        raise RuntimeError("Fault drill or cleanup failed; safe report retained, production was not a drill target")
