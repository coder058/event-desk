"""Run label-blind research on Dublin using the live worker's shared quota ledger.

Archives/evidence stay in an ignored private volume. Existing evidence is never
replaced by a shorter or divergent local file. No competition submissions occur.
"""
from __future__ import annotations

import argparse
import io
import math
import shlex
import subprocess
import tarfile
from pathlib import Path

from bootstrap import SSH

PREPARE = '''
import hashlib,io,json,os,sys,tarfile,tempfile
from pathlib import Path
root=Path('/var/lib/eventdesk/research');root.mkdir(mode=0o700,parents=True,exist_ok=True)
os.chown(root,10001,10001)
allowed={'archive/2026Q2.jsonl.gz','archive/2026Q3.jsonl.gz','quota-source-sealed.json',
         'evidence/llm-groq-2026Q2.jsonl','evidence/llm-groq-2026Q3.jsonl',
         'evidence/llm-gemini-2026Q2.jsonl','evidence/llm-gemini-2026Q3.jsonl'}
written=[]
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
 members=archive.getmembers()
 if len({m.name for m in members})!=len(members):raise ValueError('Duplicate research upload')
 for member in members:
  if not member.isfile() or member.name not in allowed:raise ValueError('Unexpected research upload')
  stream=archive.extractfile(member)
  if stream is None:raise ValueError('Missing regular member')
  raw=stream.read();path=root/member.name
  path.parent.mkdir(mode=0o700,parents=True,exist_ok=True);os.chown(path.parent,10001,10001)
  if path.exists():
   existing=path.read_bytes()
   if member.name.startswith('evidence/'):
    if existing.startswith(raw):continue
    if not raw.startswith(existing):raise ValueError('Divergent evidence upload')
   elif existing!=raw:raise ValueError('Immutable research input changed')
   else:continue
  fd,temporary=tempfile.mkstemp(prefix='.upload-',dir=path.parent)
  try:
   with os.fdopen(fd,'wb') as destination:
    destination.write(raw);destination.flush();os.fsync(destination.fileno())
   os.chmod(temporary,0o600);os.chown(temporary,10001,10001);os.replace(temporary,path)
  finally:Path(temporary).unlink(missing_ok=True)
  written.append({'name':member.name,'sha256':hashlib.sha256(raw).hexdigest()})
print(json.dumps({'private_research_files_prepared':written,'no_credentials_uploaded':True}))
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quarter", choices=("2026Q2", "2026Q3"), required=True)
    parser.add_argument("--provider", choices=("gemini", "groq"), required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--wait-local-seconds", type=float, default=0)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.count <= 0 or not math.isfinite(args.wait_local_seconds) or args.wait_local_seconds < 0:
        raise ValueError("Invalid caller research budget")
    snapshot = Path("private/quota-source-sealed.json")
    if not snapshot.is_file():
        raise RuntimeError("Stop local collectors and seal their quota ledger before transfer")
    files = {"quota-source-sealed.json": snapshot}
    for quarter in ("2026Q2", "2026Q3"):
        files["archive/"+quarter+".jsonl.gz"] = Path.home()/".eventdesk/research/archive"/(quarter+".jsonl.gz")
        for provider in ("gemini", "groq"):
            name = "llm-"+provider+"-"+quarter+".jsonl"
            source = Path("private")/name
            if source.exists():
                files["evidence/"+name] = source
    blob = io.BytesIO()
    with tarfile.open(fileobj=blob, mode="w:gz") as archive:
        for name, path in files.items():
            archive.add(path, arcname=name, recursive=False)
    result = subprocess.run(SSH+["sudo python3 -I -c "+shlex.quote(PREPARE)],
                            input=blob.getvalue(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Private research upload failed; remote details withheld")
    print(result.stdout.decode().strip(), flush=True)
    # SOURCE: same network/environment as deployed worker; no separate quota database or key copy.
    # GUESS: 256 MiB research ceiling bounds this one-off collector; not measured optimal. # UNCALIBRATED GUESS
    base = ["sudo", "docker", "run", "--rm", "--network", "eventdesk_default",
        "--env-file", "/etc/eventdesk/env", "--env-file", "/etc/eventdesk/runtime.env",
        "--volume", "/var/lib/eventdesk/research:/research", "--workdir", "/research",
        "--memory", "256m", "--read-only", "--tmpfs", "/tmp", "eventdesk-worker", "python"]
    imported = subprocess.run(SSH+[shlex.join(base+["/app/research/import_quotas.py", "--snapshot",
                                                   "/research/quota-source-sealed.json"])])
    if imported.returncode:
        raise RuntimeError("Shared quota import failed; no collection launched")
    if args.prepare_only:
        return
    command = base+["/app/research/collect_llm.py", "--archive-dir", "/research/archive",
        "--output-dir", "/research/evidence", "--quarter", args.quarter, "--provider", args.provider,
        "--count", str(args.count), "--wait-local-seconds", str(args.wait_local_seconds)]
    raise SystemExit(subprocess.run(SSH+[shlex.join(command)]).returncode)


if __name__ == "__main__":
    main()
