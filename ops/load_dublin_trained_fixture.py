"""HTTP/PG busy-day replay with the exact trained artifact and label-free archive inputs."""
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
import json,subprocess,sys,urllib.request
from pathlib import Path
data=json.load(sys.stdin)
root=Path('/srv/eventdesk');override=Path('/tmp/eventdesk-trained-fixture.yaml')
services={name:{'image':'eventdesk-worker:latest'} for name in ('api','worker','migrate','seed-model')}
for name in ('api','worker'):
 services[name]['environment']={'EVENTDESK_MODEL_PATH':'/models/local-model.joblib'}
 services[name]['volumes']=['/var/lib/eventdesk/models:/models:ro']
# GUESS: identical fixture startup probes to the previous verified replay.
services['api']['healthcheck']={'test':['CMD','python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2)"],
 'interval':'2s','timeout':'3s','retries':20}
override.write_text(json.dumps({'services':services}))
compose=['sudo','docker','compose','-p','eventdesk-trained-fixture','-f','compose.yaml','-f',str(override)]
try:
 subprocess.run(compose+['up','--no-build','--wait','--wait-timeout','60'],cwd=root,check=True)
 write="import json,os,sys;from pathlib import Path;os.umask(0o077);d=json.load(sys.stdin);Path('/tmp/archive-materials.json').write_text(json.dumps(d['materials']));Path('/tmp/trained-load.py').write_text(d['load_script'])"
 subprocess.run(compose+['exec','-T','api','python','-c',write],cwd=root,input=json.dumps(data).encode(),check=True)
 subprocess.run(compose+['exec','-T','api','python','/tmp/trained-load.py','--material-file','/tmp/archive-materials.json'],cwd=root,check=True)
 subprocess.run(['sudo','docker','cp','eventdesk-trained-fixture-api-1:/tmp/eventdesk-fixture-load.json',str(root/'reports/trained-fixture-load.json')],check=True)
finally:
 subprocess.run(compose+['logs','--no-log-prefix','--tail','5','api','worker'],cwd=root,check=False)
 subprocess.run(compose+['down'],cwd=root,check=True)
 print('production_health='+urllib.request.urlopen('http://127.0.0.1:8800/healthz').read().decode())
'''


if __name__ == "__main__":
    archive = Path.home() / ".eventdesk/research/archive/2026Q3.jsonl.gz"
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream]
    rows.sort(key=lambda row: (row["event_datetime"], row["event_id"]))
    # SOURCE: mission's 400-event replay, chosen chronologically without labels.
    materials = [{"items": [{"id": key, "content": value} for key, value in select_items(row).items()]}
                 for row in rows[:400]]
    payload = {"materials": materials, "load_script": Path("fixtures/load_test.py").read_text()}
    result = subprocess.run(SSH + ["python3 -c " + shlex.quote(REMOTE)], input=json.dumps(payload).encode())
    if result.returncode:
        raise SystemExit(result.returncode)
    copied = subprocess.run(["scp", "-i", str(Path.home() / ".ssh/lightsail-eu-west-1.pem"),
        "-oBatchMode=yes", "-oStrictHostKeyChecking=yes",
        "ubuntu@52.17.192.36:/srv/eventdesk/reports/trained-fixture-load.json",
        "reports/dublin-trained-fixture-load.json"], check=True)
    report_path = Path("reports/dublin-trained-fixture-load.json")
    report = json.loads(report_path.read_text())
    if report["worker_model_sha256"] != hashlib.sha256(Path("artifacts/local-model.joblib").read_bytes()).hexdigest():
        raise RuntimeError("Fixture worker did not use the intended trained artifact")
    report["archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    report["load_script_sha256"] = hashlib.sha256(payload["load_script"].encode()).hexdigest()
    report_path.write_text(json.dumps(report, indent=2) + "\n")
