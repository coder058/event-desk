"""Paired read-only comparison on Dublin; candidate code runs in a disposable process."""
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
import hashlib,json,statistics,sys,time,types
from pathlib import Path
import eventdesk.model as baseline_module
data=json.load(sys.stdin)
candidate=types.ModuleType('eventdesk_candidate_explanation')
exec(compile(data['source'],'candidate_explanation.py','exec'),candidate.__dict__)
models={};loads={};durations={'baseline':[],'candidate':[]};maximum_difference=0.;maximum_term_difference=0.
for name,cls in [('baseline',baseline_module.LocalModel),('candidate',candidate.LocalModel)]:
 start=time.perf_counter();models[name]=cls(Path('/models/local-model.joblib'));loads[name]=(time.perf_counter()-start)*1000
for index,items in enumerate(data['items']):
 traces={}
 for name in (('baseline','candidate') if index%2==0 else ('candidate','baseline')):
  start=time.perf_counter();traces[name]=models[name].explain(items);durations[name].append((time.perf_counter()-start)*1000)
 a,b=traces['baseline'],traces['candidate']
 assert a['kind']==b['kind']
 maximum_difference=max(maximum_difference,abs(a['prediction']-b['prediction']))
 if 'terms' in a:
  assert [t['feature'] for t in a['terms']]==[t['feature'] for t in b['terms']]
  for old,new in zip(a['terms'],b['terms']):
   for field in ('feature_value','coefficient','contribution'):
    maximum_term_difference=max(maximum_term_difference,abs(old[field]-new[field]))
  maximum_term_difference=max(maximum_term_difference,abs(a['other_terms_contribution']-b['other_terms_contribution']))
def stats(values):
 q=statistics.quantiles(values,n=100,method='inclusive')
 return {'p50_ms':statistics.median(values),'p95_ms':q[94],'max_ms':max(values),'sum_ms':sum(values)}
print(json.dumps({'kind':'paired_read_only_explanation_comparison','events':len(data['items']),
 'model_sha256':models['baseline'].sha256,'baseline_source_sha256':hashlib.sha256(Path(baseline_module.__file__).read_bytes()).hexdigest(),
 'candidate_source_sha256':hashlib.sha256(data['source'].encode()).hexdigest(),'cold_load_ms':loads,
 'baseline':stats(durations['baseline']),'candidate':stats(durations['candidate']),
 'max_prediction_difference':maximum_difference,'max_displayed_math_difference':maximum_term_difference,
 'term_names_identical':True,'limits':'Alternating paired order, same inputs/host/process; no HTTP, DB, official score or capacity measured'}))
'''


if __name__ == "__main__":
    archive = Path.home() / ".eventdesk/research/archive/2026Q3.jsonl.gz"
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    rows.sort(key=lambda row: (row["event_datetime"], row["event_id"]))
    # SOURCE: same chronological 400-event plumbing replay; labels are never transmitted.
    payload = {"items": [select_items(row) for row in rows[:400]],
               "source": Path("src/eventdesk/model.py").read_text()}
    result = subprocess.run(SSH + ["sudo docker exec -i eventdesk-worker-1 python -c " + shlex.quote(REMOTE)],
                            input=json.dumps(payload).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Paired explanation profile failed; private input/stderr withheld")
    report = json.loads(result.stdout)
    report["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    Path("reports/explanation-comparison.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
