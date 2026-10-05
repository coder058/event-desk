"""Owner-authorized operations; secrets travel only through SSH stdin."""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path

SSH = ["ssh", "-T", "-i", str(Path.home() / ".ssh/lightsail-eu-west-1.pem"),
       "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "ubuntu@52.17.192.36"]


def install_secrets() -> None:
    source = Path.home() / ".eventdesk/.env"
    raw = source.read_bytes()
    names = {line.split(b"=", 1)[0].strip().decode(): bool(line.split(b"=", 1)[1].strip())
             for line in raw.splitlines() if b"=" in line and not line.lstrip().startswith(b"#")}
    required = ("EM_API_KEY", "EM_WEBHOOK_SECRET", "GEMINI_API_KEY", "GROQ_API_KEY")
    if not all(names.get(name) for name in required):
        raise SystemExit("Required secret variable missing; values withheld")
    code = '''import os,sys,tempfile,json
from pathlib import Path
d=Path('/etc/eventdesk');d.mkdir(mode=0o700,exist_ok=True);os.chmod(d,0o700)
target=d/'env'
if target.exists(): raise SystemExit('Target exists; refusing silent credential replacement')
fd,tmp=tempfile.mkstemp(prefix='.env-',dir=d)
with os.fdopen(fd,'wb') as f:
 f.write(sys.stdin.buffer.read());f.flush();os.fsync(f.fileno())
os.chmod(tmp,0o600);os.chown(tmp,0,0);os.replace(tmp,target)
print(json.dumps({'path':str(target),'mode':oct(target.stat().st_mode&0o777),'uid':target.stat().st_uid}))
'''
    result = subprocess.run(SSH + ["sudo python3 -c " + shlex.quote(code)], input=raw,
                            capture_output=True, check=False)
    if result.returncode:
        raise SystemExit("Secret installation failed; remote output withheld")
    print(result.stdout.decode().strip())
    print(json.dumps({name: names.get(name, False) for name in required}))


def freeze() -> None:
    timers = ["ai-ocaml-fx-connection", "ai-ocaml-stock-paper", "ai-ocaml-stock-quote-audit",
              "ai-ocaml-stock-session-audit", "jane-five-minute-bars", "jane-market-pipeline",
              "jane-markov-shadow", "jane-multi-paper", "jane-multi-timeframe-shadow", "jane-telemetry"]
    captures = ["ai-ocaml-paper-order-capture", "ai-ocaml-stock-capture",
                "jane-hyperliquid-capture", "jane-market-capture"]
    code = '''import subprocess,json,urllib.request
from pathlib import Path
env={}
for line in Path('/etc/jsbot-paper.env').read_text().splitlines():
 if '=' in line and not line.lstrip().startswith('#'):
  k,v=line.split('=',1);env[k.strip()]=v.strip().strip('"').strip("'")
headers={'APCA-API-KEY-ID':env['APCA_API_KEY_ID'],'APCA-API-SECRET-KEY':env['APCA_API_SECRET_KEY']}
def read(path):
 with urllib.request.urlopen(urllib.request.Request('https://paper-api.alpaca.markets/v2/'+path,headers=headers),timeout=15) as r:return json.load(r)
positions=read('positions');orders=read('orders?status=open')
if orders or any(p['symbol']!='AAPL' for p in positions):raise SystemExit('Freeze blocked: holdings or orders require reconciliation')
timers=TIMERS;captures=CAPTURES
subprocess.run(['systemctl','disable','--now']+[x+'.timer' for x in timers],check=True,capture_output=True)
subprocess.run(['systemctl','stop']+[x+'.service' for x in timers],check=True,capture_output=True)
subprocess.run(['systemctl','disable','--now']+[x+'.service' for x in captures],check=True,capture_output=True)
units=[x+'.timer' for x in timers]+[x+'.service' for x in timers+captures]
state={x:subprocess.run(['systemctl','is-active',x],capture_output=True,text=True).stdout.strip() for x in units}
Path('/etc/eventdesk/old-service-state.json').write_text(json.dumps(state,indent=2))
print(json.dumps({'unit_states':state,'positions':[p['symbol'] for p in read('positions')],'open_orders':len(read('orders?status=open'))}))
'''.replace("TIMERS", repr(timers)).replace("CAPTURES", repr(captures))
    result = subprocess.run(SSH + ["sudo python3 -c " + shlex.quote(code)], capture_output=True)
    if result.returncode:
        raise SystemExit("Freeze failed; inspect service status without exposing environment")
    print(result.stdout.decode().strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["install-secrets", "freeze"])
    args = parser.parse_args()
    install_secrets() if args.action == "install-secrets" else freeze()
