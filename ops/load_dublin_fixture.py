"""Run the mission's load test on an isolated Dublin fixture database and network."""
from __future__ import annotations

import subprocess

from bootstrap import SSH

REMOTE = '''
import json, subprocess, urllib.request
from pathlib import Path
root=Path('/srv/eventdesk')
override=Path('/tmp/eventdesk-fixture-images.yaml')
services={name:{'image':'eventdesk-worker:latest'} for name in ('api','worker','migrate','seed-model')}
# GUESS: fixture startup probe timing, distinct from the official event ACK budget.
services['api']['healthcheck']={'test':['CMD','python','-c',"import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=2)"],
 'interval':'2s','timeout':'3s','retries':20}
override.write_text(json.dumps({'services':services}))
compose=['sudo','docker','compose','-p','eventdesk-fixture','-f','compose.yaml','-f',str(override)]
try:
 subprocess.run(compose+['up','--no-build','--wait','--wait-timeout','60'],cwd=root,check=True)
 subprocess.run(['sudo','docker','cp',str(root/'fixtures/receipt_concurrency.py'),
                 'eventdesk-fixture-api-1:/tmp/receipt_concurrency.py'],check=True)
 subprocess.run(compose+['exec','-T','api','python','/tmp/receipt_concurrency.py'],cwd=root,check=True)
 subprocess.run(compose+['exec','-T','api','python','fixtures/load_test.py'],cwd=root,check=True)
 report=root/'reports/dublin-fixture-load.json'
 subprocess.run(['sudo','docker','cp','eventdesk-fixture-api-1:/tmp/eventdesk-fixture-load.json',str(report)],check=True)
 print(report.read_text())
finally:
 subprocess.run(['sudo','docker','inspect','--format','{{json .State.Health}}','eventdesk-fixture-api-1'],check=False)
 subprocess.run(compose+['logs','--no-log-prefix','--tail','20','api','worker'],cwd=root,check=True)
 subprocess.run(compose+['down'],cwd=root,check=True)
 print('production_health='+urllib.request.urlopen('http://127.0.0.1:8800/healthz').read().decode())
'''


if __name__ == "__main__":
    result = subprocess.run(SSH + ["python3 -"], input=REMOTE.encode())
    raise SystemExit(result.returncode)
