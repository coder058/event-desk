"""Retain the exact completed private research attempts locally, without credential access."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path

from bootstrap import SSH

REMOTE = '''
import base64,json
from pathlib import Path
root=Path('/var/lib/eventdesk/research/evidence')
records={}
for provider in ('gemini','groq'):
 for quarter in ('2026Q2','2026Q3'):
  name='llm-'+provider+'-'+quarter+'.jsonl';path=root/name
  if not path.exists():continue
  if path.is_symlink() or not path.is_file():raise ValueError('Unsafe evidence file')
  raw=path.read_bytes()
  # A collector must be stopped; a partial append is not accepted as retained evidence.
  if not raw.endswith(b'\\n'):raise ValueError('Unfinished evidence append')
  for line in raw.decode('utf-8').splitlines():json.loads(line)
  records[name]=base64.b64encode(raw).decode('ascii')
print(json.dumps(records))
'''


def main() -> None:
    result = subprocess.run(SSH+["sudo python3 -I -c "+shlex.quote(REMOTE)], capture_output=True)
    if result.returncode:
        raise RuntimeError("Private evidence retrieval failed; remote details withheld")
    records = json.loads(result.stdout)
    allowed = {"llm-"+provider+"-"+quarter+".jsonl" for provider in ("groq", "gemini")
               for quarter in ("2026Q2", "2026Q3")}
    if not isinstance(records, dict) or set(records)-allowed:
        raise ValueError("Unexpected research evidence export")
    saved = []
    for name, encoded in records.items():
        raw = base64.b64decode(encoded, validate=True)
        target = Path("private")/name
        if target.is_symlink() or (target.exists() and not raw.startswith(target.read_bytes())):
            raise ValueError("Evidence retrieval would replace divergent local attempts")
        descriptor, temporary = tempfile.mkstemp(prefix=".evidence-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        saved.append({"name": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    print(json.dumps({"private_evidence_retained": saved, "credential_files_read": False}))


if __name__ == "__main__":
    main()
