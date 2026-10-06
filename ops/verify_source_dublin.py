"""Verify all Alembic migrations and source races in a new, disposable Dublin PG database."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

CHILD = '''
import json,os,re,runpy,sys
from sqlalchemy.engine import make_url
from sqlalchemy import create_engine,text
from alembic.config import Config
from alembic import command
database=sys.argv[1]
if not re.fullmatch(r"eventdesk_source_\\d+",database): raise ValueError("Invalid isolated database")
url=make_url(os.environ['DATABASE_URL'])
if url.database==database: raise ValueError("Production must not be the target")
os.environ['DATABASE_URL']=url.set(database=database).render_as_string(hide_password=False)
os.environ['EVENTDESK_FIXTURE_MODE']='true'
command.upgrade(Config('alembic.ini'),'head')
runpy.run_path('fixtures/source_concurrency.py',run_name='__main__')
engine=create_engine(os.environ['DATABASE_URL'])
with engine.connect() as connection:
 schema=connection.scalar(text('SELECT version_num FROM alembic_version'))
print(json.dumps({'schema':schema,'target':'disposable_database','production_target':False}))
engine.dispose()
'''
REMOTE = '''
import json,subprocess,sys,time
data=json.load(sys.stdin);database='eventdesk_source_'+str(time.time_ns())
db=['sudo','docker','exec','eventdesk-db-1']
subprocess.run(db+['createdb','-U','eventdesk',database],capture_output=True,check=True)
try:
 result=subprocess.run(['sudo','docker','exec','-i','eventdesk-worker-1','python','-c',data['script'],database],capture_output=True)
 if result.returncode: raise RuntimeError('Isolated source verification failed; diagnostic output withheld')
 rows=[json.loads(line) for line in result.stdout.decode().splitlines()]
 print(json.dumps({'checks':rows,'external_requests':0,'limits':'Actual disposable PostgreSQL migration/concurrency fixture, synthetic bytes; no daily SEC collector.'}))
finally:
 subprocess.run(db+['dropdb','-U','eventdesk',database],capture_output=True,check=True)
'''


def main() -> None:
    result = subprocess.run(SSH+["python3 -c "+shlex.quote(REMOTE)],
        input=json.dumps({"script": CHILD}).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Isolated source verification/cleanup failed; output withheld")
    report = json.loads(result.stdout)
    Path("reports/dublin-source-fixture.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
