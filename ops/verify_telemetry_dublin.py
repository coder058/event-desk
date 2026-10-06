"""Verify local OTel export in an isolated fixture process inside the deployed image."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

REMOTE = '''
import asyncio,json,logging,tempfile,time
from pathlib import Path
import httpx
from eventdesk.config import Settings,Submission
from eventdesk.model import LocalModel
from eventdesk.schemas import Event
from eventdesk.store import Store
from eventdesk.telemetry import Telemetry
from eventdesk.worker import Worker
logging.basicConfig(level=logging.INFO,format='%(message)s')
logging.getLogger('httpx').setLevel(logging.WARNING)
async def main():
 with tempfile.TemporaryDirectory(prefix='eventdesk-otel-fixture-') as directory:
  store=Store('sqlite:///'+str(Path(directory)/'fixture.sqlite'));store.initialize_fixture()
  settings=Settings(str(store.engine.url),Path('/models/local-model.joblib'),
    {'s1':Submission('s1','fixture-only','fixture-only')},True,frozenset())
  model=LocalModel(settings.model_path);telemetry=Telemetry()
  event=Event(id='telemetry-fixture',event_id='telemetry-fixture',event_type='EARNINGS_RELEASE',
    knowledge_cutoff='2026-01-01T00:00:00Z',focal_assets=[{'identifier_type':'TICKER','identifier_value':'FIXTURE'}],
    fixture_materials={'items':[{'id':'earnings-call-facts','content':['never-export-fixture-source']} ]})
  store.receive('s1',event.id,event.model_dump_json().encode(),event,time.time())
  def reject_network(request): raise AssertionError('Fixture attempted a network request')
  try:
   async with httpx.AsyncClient(transport=httpx.MockTransport(reject_network)) as http:
    await Worker(settings,store,model,http,telemetry=telemetry).process_claimed(store.claim(time.time()))
   assert store.health()['states']=={'simulated':1}
   print(json.dumps({'fixture_complete':True,'model_sha256':model.sha256}))
  finally:
   telemetry.shutdown();store.engine.dispose()
asyncio.run(main())
'''


if __name__ == "__main__":
    result = subprocess.run(SSH+["sudo docker exec eventdesk-worker-1 python -c "+shlex.quote(REMOTE)],
                            capture_output=True)
    if result.returncode:
        raise RuntimeError("Isolated deployed telemetry fixture failed; output withheld")
    lines = result.stdout.decode().splitlines()+result.stderr.decode().splitlines()
    records = [json.loads(line) for line in lines if line.startswith("{")]
    spans = [record for record in records if record.get("kind") == "otel_span"]
    if {record["stage"] for record in spans} != {"eventdesk.job", "eventdesk.local_inference"}:
        raise RuntimeError("Deployed OTel stages missing")
    if "never-export-fixture-source" in json.dumps(spans):
        raise RuntimeError("Fixture source leaked into telemetry")
    if not all(record.get("attributes", {}).get("eventdesk.fixture") is True
               for record in spans if record["stage"] == "eventdesk.job"):
        raise RuntimeError("Fixture span lost simulation label")
    report = {"kind": "isolated_deployed_otel_fixture", "spans": spans,
        "source_content_excluded": True, "network_requests": 0,
        "limits": "Actual local SDK export from a fixture process, not official prediction or distributed receipt tracing"}
    Path("reports/dublin-telemetry-fixture.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report))
