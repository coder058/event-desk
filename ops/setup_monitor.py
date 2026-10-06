"""Install only this project's independent operational timer on the existing Dublin VPS."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

REMOTE = '''
import json,os,subprocess,sys
from pathlib import Path
data=json.load(sys.stdin)
directory=Path('/var/lib/eventdesk/monitor');directory.mkdir(parents=True,mode=0o700,exist_ok=True);os.chmod(directory,0o700)
script=Path('/usr/local/libexec/eventdesk-monitor.py');script.write_text(data['script']);os.chmod(script,0o700)
for name in ('eventdesk-monitor.service','eventdesk-monitor.timer'):
 path=Path('/etc/systemd/system')/name;path.write_text(data[name]);os.chmod(path,0o644)
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable','--now','eventdesk-monitor.timer'],check=True,capture_output=True)
subprocess.run(['systemctl','start','eventdesk-monitor.service'],check=True,capture_output=True)
state=json.loads((directory/'state.json').read_text())
print(json.dumps({'timer_state':subprocess.check_output(['systemctl','is-active','eventdesk-monitor.timer']).decode().strip(),
 'service_result':subprocess.check_output(['systemctl','show','eventdesk-monitor.service','--property=Result','--value']).decode().strip(),
 'observation':state}))
'''


if __name__ == "__main__":
    payload = {"script": Path("ops/monitor.py").read_text(encoding="utf-8"),
        **{name: Path("ops", name).read_text(encoding="utf-8")
           for name in ("eventdesk-monitor.service", "eventdesk-monitor.timer")}}
    result = subprocess.run(SSH+["sudo python3 -c "+shlex.quote(REMOTE)],
                            input=json.dumps(payload).encode(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Project monitor installation failed; output withheld")
    print(result.stdout.decode().strip())
