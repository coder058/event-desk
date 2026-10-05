"""Read-only full-quarter single-event inference timing on the actual Dublin container."""
from __future__ import annotations

import gzip
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

from eventdesk.materials import select_items
from eventdesk.model import LocalModel

REMOTE = '''
import hashlib,json,statistics,time
from pathlib import Path
started=time.perf_counter()
from eventdesk.model import LocalModel
model=LocalModel(Path('/models/local-model.joblib'))
load_ms=(time.perf_counter()-started)*1000
data=json.load(__import__('sys').stdin)
durations=[];predictions=[]
for items in data['items']:
 start=time.perf_counter()
 predictions.append(model.predict(items))
 durations.append((time.perf_counter()-start)*1000)
# SOURCE: inclusive empirical percentile convention, reported with the exact sample count.
quantiles=statistics.quantiles(durations,n=100,method='inclusive')
report={'kind':'archived_single_event_inference_on_dublin','model_sha256':model.sha256,
 'archive_sha256':data['archive_sha256'],'events':len(durations),'model_cold_load_ms':load_ms,
 'single_event_p50_ms':statistics.median(durations),'single_event_p95_ms':quantiles[94],
 'single_event_p99_ms':quantiles[98],'single_event_max_ms':max(durations),
 'prediction_sha256':hashlib.sha256(json.dumps(predictions).encode()).hexdigest(),'predictions':predictions,
 'limits':'Archived Q3 inputs; no provider/material network, durable ACK, submission latency or live score measured'}
print(json.dumps(report))
'''


if __name__ == "__main__":
    archive = Path.home() / ".eventdesk/research/archive/2026Q3.jsonl.gz"
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        items = [select_items(json.loads(line)) for line in stream]
    payload = {"items": items, "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
    command = "sudo docker exec -i eventdesk-worker-1 python -c " + shlex.quote(REMOTE)
    result = subprocess.run(SSH + [command], input=json.dumps(payload).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Read-only benchmark failed; private input and stderr withheld")
    report = json.loads(result.stdout)
    if report["model_sha256"] != hashlib.sha256(Path("artifacts/local-model.joblib").read_bytes()).hexdigest():
        raise RuntimeError("Container benchmark used a different model")
    remote_predictions = report.pop("predictions")
    local = LocalModel(Path("artifacts/local-model.joblib"))
    local_predictions = [local.predict(item) for item in items]
    report["max_absolute_windows_dublin_difference"] = max(
        abs(left - right) for left, right in zip(local_predictions, remote_predictions, strict=True))
    Path("reports/dublin-inference.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
