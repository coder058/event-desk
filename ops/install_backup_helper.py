"""Replace only the reviewed existing project backup helper; preserve keys/timers."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

REMOTE = '''
import json,os,sys,tempfile
from pathlib import Path
data=json.load(sys.stdin);path=Path('/usr/local/libexec/eventdesk-backup.py')
compile(data['script'],str(path),'exec')
fd,temporary=tempfile.mkstemp(prefix='.eventdesk-backup-',dir=path.parent)
try:
 with os.fdopen(fd,'w') as stream:
  stream.write(data['script']);stream.flush();os.fsync(stream.fileno())
 os.chmod(temporary,0o700);os.replace(temporary,path)
finally:Path(temporary).unlink(missing_ok=True)
print(json.dumps({'reviewed_backup_helper_installed':True,'keys_and_timer_preserved':True}))
'''


if __name__ == "__main__":
    payload = json.dumps({"script": Path("ops/backup.py").read_text(encoding="utf-8")}).encode()
    result = subprocess.run(SSH+["sudo python3 -I -c "+shlex.quote(REMOTE)], input=payload, capture_output=True)
    if result.returncode:
        raise RuntimeError("Scoped helper installation failed; private output withheld")
    print(result.stdout.decode().strip())
