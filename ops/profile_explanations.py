"""Read-only staged timing with label-free inputs from the trained-model busy-day replay."""
from __future__ import annotations

import gzip
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

from eventdesk.materials import select_items

REMOTE = '''
import json,statistics,sys,time
from pathlib import Path
from eventdesk.model import LocalModel
model=LocalModel(Path('/models/local-model.joblib'))
data=json.load(sys.stdin);predict=[];explain=[];differences=[]
for item in data['items']:
 start=time.perf_counter();value=model.predict(item);predict.append((time.perf_counter()-start)*1000)
 start=time.perf_counter();trace=model.explain(item);explain.append((time.perf_counter()-start)*1000)
 differences.append(abs(value-trace['prediction']))
def stats(values):
 quantiles=statistics.quantiles(values,n=100,method='inclusive')
 return {'p50_ms':statistics.median(values),'p95_ms':quantiles[94],'max_ms':max(values),'sum_ms':sum(values)}
print(json.dumps({'kind':'read_only_dublin_prediction_and_explanation_profile','events':len(predict),
 'model_sha256':model.sha256,'predict':stats(predict),'explain':stats(explain),
 'max_prediction_explanation_difference':max(differences),
 'limits':'Serial archived-input computation; no material HTTP, DB, submission, score or capacity measured'}))
'''


if __name__ == "__main__":
    archive = Path.home() / ".eventdesk/research/archive/2026Q3.jsonl.gz"
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        records = [json.loads(line) for line in stream]
    records.sort(key=lambda record: (record["event_datetime"], record["event_id"]))
    # SOURCE: same 400-event chronological fixture selection; no labels transmitted.
    payload = {"items": [select_items(record) for record in records[:400]]}
    result = subprocess.run(SSH + ["sudo docker exec -i eventdesk-worker-1 python -c " + shlex.quote(REMOTE)],
                            input=json.dumps(payload).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Read-only profile failed; private input/stderr withheld")
    report = json.loads(result.stdout)
    report["source_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    report["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    output = Path("reports/explanation-profile-" + report["source_sha"][:7] + ".json")
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
