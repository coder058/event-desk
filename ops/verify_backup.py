"""Decrypt/hash-check remotely and restore only into a new disposable Dublin database."""
from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path

from bootstrap import SSH
from setup_backup import FRANKFURT, remote

VERIFY = '''
import hashlib,json,subprocess,sys,tarfile,tempfile
from pathlib import Path
data=json.load(sys.stdin)
path=Path('/home/ubuntu/eventdesk-backups')/data['file']
assert path.name.startswith('eventdesk-') and path.name.endswith('.tar.gz.age')
assert hashlib.sha256(path.read_bytes()).hexdigest()==data['ciphertext_sha256']
with tempfile.TemporaryDirectory(prefix='eventdesk-restore-') as temporary:
 archive=Path(temporary)/'backup.tar.gz'
 subprocess.run(['age','-d','-i','/etc/eventdesk-backup/identity.txt','-o',str(archive),str(path)],capture_output=True,check=True)
 with tarfile.open(archive,'r:gz') as tar:
  members=tar.getmembers()
  assert all(member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts for member in members)
  assert len({member.name for member in members})==len(members)
  manifest=json.load(tar.extractfile('manifest.json'))
  assert {member.name for member in members}==set(manifest['files'])|{'manifest.json'}
  for name,metadata in manifest['files'].items():
   digest=hashlib.sha256();size=0
   with tar.extractfile(name) as stream:
    while chunk:=stream.read(65536):digest.update(chunk);size+=len(chunk)
   assert digest.hexdigest()==metadata['sha256'] and size==metadata['bytes']
  assert manifest['files']['local-model.joblib']['sha256']==data['model_sha256']
 print(json.dumps({'archive_files_verified':len(manifest['files']),'model_sha256':data['model_sha256']}))
'''

EXPORT_DUMP = '''
import subprocess,sys,tarfile,tempfile
from pathlib import Path
path=Path('/home/ubuntu/eventdesk-backups')/sys.argv[1]
with tempfile.TemporaryDirectory(prefix='eventdesk-dump-') as temporary:
 archive=Path(temporary)/'backup.tar.gz'
 subprocess.run(['age','-d','-i','/etc/eventdesk-backup/identity.txt','-o',str(archive),str(path)],capture_output=True,check=True)
 with tarfile.open(archive,'r:gz') as tar:
  with tar.extractfile('database.dump') as stream:
   while chunk:=stream.read(65536):sys.stdout.buffer.write(chunk)
'''
# GUESS: 64 KiB buffers above are bounded streaming choices, not data/model parameters.


def main() -> None:
    report = json.loads(remote(SSH, "from pathlib import Path;print(Path('/var/lib/eventdesk/backups/latest.json').read_text())"))
    if Path(report["file"]).name != report["file"]:
        raise ValueError("Unexpected backup filename")
    verified = json.loads(remote(FRANKFURT, VERIFY, json.dumps(report).encode()))
    database = "eventdesk_restore_" + str(time.time_ns())
    command = "sudo docker exec eventdesk-db-1 "
    # Exact newly created test database name is retained; the production database is never a restore/drop target.
    created = subprocess.run(SSH + [command + "createdb -U eventdesk " + database], capture_output=True)
    if created.returncode:
        raise RuntimeError("Isolated restore database creation failed; private stderr withheld")
    try:
        exporter = subprocess.Popen(FRANKFURT + ["sudo python3 -I -c " + shlex.quote(EXPORT_DUMP)
                                   + " " + shlex.quote(report["file"])], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            restored = subprocess.run(SSH + ["sudo docker exec -i eventdesk-db-1 pg_restore -U eventdesk "
                "--no-owner --no-privileges --exit-on-error -d " + database], stdin=exporter.stdout,
                capture_output=True)
            assert exporter.stdout is not None
            exporter.stdout.close()
            # communicate() must not start a Windows pipe reader on the already consumed/closed stdout.
            exporter.stdout = None
            exporter.communicate()
            if restored.returncode or exporter.returncode:
                raise RuntimeError("Isolated pg_restore failed; database contents and stderr withheld")
        finally:
            if exporter.poll() is None:
                exporter.kill()
                exporter.communicate()
        query = ("SELECT version_num FROM alembic_version; SELECT count(*) FROM jobs; "
                 "SELECT count(*) FROM deliveries; SELECT count(*) FROM competition_calendars; "
                 "SELECT count(*) FROM competition_observations;")
        checked = subprocess.run(SSH + [command + "psql -U eventdesk -d " + database + " -At -c " + shlex.quote(query)],
                                 capture_output=True, check=True)
        rows = checked.stdout.decode().splitlines()
        # SOURCE: this probe returns schema plus four exact table counts, including schema-008 observations.
        if len(rows) != 5:
            raise RuntimeError("Unexpected isolated restore schema probe")
        report.update(verified)
        report.update({"restore_verified": True, "restored_schema": rows[0],
                       "restored_jobs": int(rows[1]), "restored_deliveries": int(rows[2]),
                       "restored_competition_calendars": int(rows[3]),
                       "restored_competition_observations": int(rows[4]),
                       "limits": "One encrypted backup hash-check and isolated DB restore; production was not overwritten"})
        Path("reports/backup-restore.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
    finally:
        removed = subprocess.run(SSH + [command + "dropdb -U eventdesk " + database], capture_output=True)
        if removed.returncode:
            raise RuntimeError("Disposable restore database cleanup failed; production untouched")


if __name__ == "__main__":
    main()
