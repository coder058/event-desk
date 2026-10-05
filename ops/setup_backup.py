"""One scoped bootstrap for the two existing hosts; keys stay on their respective hosts."""
from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH

FRANKFURT = ["ssh", "-T", "-i", str(Path.home() / ".ssh/lightsail-eu-central-1.pem"),
             "-oBatchMode=yes", "-oStrictHostKeyChecking=yes", "-oConnectTimeout=15",
             "ubuntu@63.183.206.174"]


def remote(host: list[str], source: str, payload: bytes = b"") -> str:
    result = subprocess.run(host + ["sudo python3 -c " + shlex.quote(source)], input=payload,
                            capture_output=True)
    if result.returncode:
        raise RuntimeError("Scoped backup setup failed; private stderr withheld")
    return result.stdout.decode().strip()


def main() -> None:
    recipient = remote(FRANKFURT, '''
import os,subprocess
from pathlib import Path
directory=Path('/etc/eventdesk-backup');directory.mkdir(mode=0o700,exist_ok=True)
identity=directory/'identity.txt'
if not identity.exists():
 subprocess.run(['age-keygen','-o',str(identity)],capture_output=True,check=True)
os.chmod(identity,0o600)
print(subprocess.check_output(['age-keygen','-y',str(identity)]).decode().strip())
''')
    if not recipient.startswith("age1") or len(recipient.splitlines()) != 1:
        raise RuntimeError("Unexpected public age recipient")
    public_key = remote(SSH, '''
import os,subprocess
from pathlib import Path
key=Path('/etc/eventdesk/backup_ed25519')
if not key.exists():
 subprocess.run(['ssh-keygen','-t','ed25519','-N','','-C','eventdesk-backup-dublin','-f',str(key)],
                capture_output=True,check=True)
os.chmod(key,0o600)
print(key.with_suffix('.pub').read_text().strip())
''')
    if not public_key.startswith("ssh-ed25519 ") or len(public_key.splitlines()) != 1:
        raise RuntimeError("Unexpected backup public SSH key")
    payload = json.dumps({"public_key": public_key,
                         "receiver": Path("ops/backup_receiver.py").read_text(encoding="utf-8")}).encode()
    remote(FRANKFURT, '''
import json,os,pwd,sys
from pathlib import Path
data=json.load(sys.stdin);account=pwd.getpwnam('ubuntu')
directory=Path('/home/ubuntu/eventdesk-backups');directory.mkdir(mode=0o700,exist_ok=True)
os.chmod(directory,0o700);os.chown(directory,account.pw_uid,account.pw_gid)
script=Path('/usr/local/libexec/eventdesk-backup-receive.py');script.parent.mkdir(parents=True,exist_ok=True)
script.write_text(data['receiver']);os.chmod(script,0o755)
authorized=Path('/home/ubuntu/.ssh/authorized_keys');existing=authorized.read_text()
line='from="52.17.192.36",restrict,command="/usr/bin/python3 -I /usr/local/libexec/eventdesk-backup-receive.py" '+data['public_key']
if data['public_key'] not in existing:
 with authorized.open('a') as stream:stream.write(('' if existing.endswith('\\n') else '\\n')+line+'\\n')
os.chmod(authorized,0o600)
print('restricted_receive_key_installed')
''', payload)
    known = subprocess.check_output(["ssh-keygen", "-F", "63.183.206.174",
                                     "-f", str(Path.home() / ".ssh/known_hosts")]).decode()
    known_lines = "\n".join(line for line in known.splitlines() if line and not line.startswith("#")) + "\n"
    if not known_lines.strip():
        raise RuntimeError("Existing owner-pinned Frankfurt host key is missing")
    payload = json.dumps({"recipient": recipient, "destination": "ubuntu@63.183.206.174",
                         "known_hosts": known_lines,
                         "script": Path("ops/backup.py").read_text(encoding="utf-8")}).encode()
    remote(SSH, '''
import json,os,sys
from pathlib import Path
data=json.load(sys.stdin)
directory=Path('/etc/eventdesk')
config=directory/'backup.json';config.write_text(json.dumps({'recipient':data['recipient'],'destination':data['destination']}))
hosts=directory/'backup_known_hosts';hosts.write_text(data['known_hosts'])
for path in (config,hosts):os.chmod(path,0o600)
script=Path('/usr/local/libexec/eventdesk-backup.py');script.parent.mkdir(parents=True,exist_ok=True)
script.write_text(data['script']);os.chmod(script,0o700)
print('encrypted_backup_configuration_installed')
''', payload)
    print("Backup setup finished; no private key or secret-file values transferred to this terminal")


if __name__ == "__main__":
    main()
