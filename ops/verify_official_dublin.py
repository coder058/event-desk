"""Verify actual isolated observer, schema and public aggregates without secrets."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

PROBE = '''
import json,os
import hashlib
from pathlib import Path
from sqlalchemy import text,select,func
from sqlalchemy.orm import Session
from eventdesk.store import Store,CompetitionCalendar,CompetitionObservation
import eventdesk.competition
store=Store(os.environ['DATABASE_URL'])
with Session(store.engine) as session:
 print(json.dumps({'schema':session.scalar(text('SELECT version_num FROM alembic_version')),
  'calendar_versions':session.scalar(select(func.count()).select_from(CompetitionCalendar)),
  'health_observations':session.scalar(select(func.count()).select_from(CompetitionObservation)),
  'observer_source_lf_sha256':hashlib.sha256(Path(eventdesk.competition.__file__).read_text(encoding='utf-8').encode()).hexdigest()}))
'''
REMOTE = '''
import json,subprocess,sys,urllib.request
probe=json.load(sys.stdin)['probe']
with urllib.request.urlopen('http://127.0.0.1:8800/api/competition',timeout=5) as response: official=json.load(response)
with urllib.request.urlopen('http://127.0.0.1:8800/healthz',timeout=5) as response: health=json.load(response)
database=json.loads(subprocess.check_output(['sudo','docker','exec','eventdesk-official-observer-1','python','-c',probe]))
observer=json.loads(subprocess.check_output(['sudo','docker','inspect','--format','{{json .State}}','eventdesk-official-observer-1']))
print(json.dumps({'official_observations':official,'schema_counts':database,
 'observer_running':observer['Running'],'observer_oom_killed':observer['OOMKilled'],
 'worker_health':health,'limits':'Actual read-only API snapshots; no official webhook or score eligibility verified'}))
'''


if __name__ == "__main__":
    result = subprocess.run(SSH+["python3 -c "+shlex.quote(REMOTE)],
                            input=json.dumps({"probe": PROBE}).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Deployed observer verification failed; output withheld")
    report = json.loads(result.stdout)
    if (report["schema_counts"]["schema"] != "008_competition_observations"
            or not report["observer_running"] or report["observer_oom_killed"]):
        raise RuntimeError("Observer/schema deployment not verified")
    observations = report["official_observations"]
    for slot in observations["configured_slots"]:
        if (observations["submissions"].get(slot, {}).get("collector") or {}).get("state") != "observed":
            raise RuntimeError("Configured submission lacks verified observation")
    if report["worker_health"]["worker"]["state"] != "recent_heartbeat":
        raise RuntimeError("Prediction worker did not remain healthy")
    Path("reports/dublin-official-observations.json").write_text(json.dumps(report, indent=2)+"\n",
                                                                encoding="utf-8")
    print(json.dumps(report))
