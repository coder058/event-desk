"""Deploy this reviewed source and trusted trained artifact to the existing VPS."""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
from pathlib import Path

from bootstrap import SSH
from secret_scan import scan


def remote_python(code: str, data: bytes = b"") -> None:
    result = subprocess.run(SSH + ["sudo python3 -c " + shlex.quote(code)], input=data,
                            capture_output=True)
    if result.returncode:
        raise RuntimeError("Remote deployment step failed; output withheld to protect environment")
    print(result.stdout.decode().strip())


def source_bundle(root: Path) -> tuple[bytes, str]:
    """Deploy committed bytes only; a dirty/untracked source cannot inherit a green CI claim."""
    git = ["git", "-C", str(root)]
    if subprocess.check_output(git+["status", "--porcelain"]).strip():
        raise RuntimeError("Commit and verify all source changes before deployment")
    revision = subprocess.check_output(git+["rev-parse", "HEAD"]).decode().strip()
    return subprocess.check_output(git+["archive", "--format=tar.gz", revision]), revision


def main() -> None:
    root = Path.cwd()
    if scan(root, Path.home() / ".eventdesk/.env"):
        raise RuntimeError("Secret scan failed")
    model = root / "artifacts/local-model.joblib"
    if not model.is_file():
        raise RuntimeError("Train and evaluate the artifact first")
    blob, revision = source_bundle(root)
    raw_model = model.read_bytes()
    declaration = json.loads((root/"competition-config.json").read_text(encoding="utf-8"))
    if hashlib.sha256(raw_model).hexdigest() != declaration["model_sha256"]:
        raise RuntimeError("Refusing to replace the deployed model with undeclared bytes")
    print("committed_source="+revision)
    remote_python("from pathlib import Path; Path('/srv/eventdesk').mkdir(exist_ok=True)")
    result = subprocess.run(SSH + ["sudo tar -xzf - -C /srv/eventdesk --no-same-owner"], input=blob)
    if result.returncode:
        raise RuntimeError("Source transfer failed")
    remote_python("""from pathlib import Path
import os,sys,hashlib
directory=Path('/var/lib/eventdesk/models');directory.mkdir(parents=True,exist_ok=True)
raw=sys.stdin.buffer.read();temporary=directory/'model.upload'
temporary.write_bytes(raw);os.chmod(temporary,0o644);os.replace(temporary,directory/'local-model.joblib')
print('model_sha256='+hashlib.sha256(raw).hexdigest())
""", raw_model)
    remote_python("""from pathlib import Path
import os,secrets,json
directory=Path('/etc/eventdesk')
db=directory/'database.env';runtime=directory/'runtime.env'
if not db.exists():
 password=secrets.token_urlsafe(32)
 db.write_text('POSTGRES_DB=eventdesk\\nPOSTGRES_USER=eventdesk\\nPOSTGRES_PASSWORD='+password+'\\n')
 os.chmod(db,0o600)
else:
 env=dict(line.split('=',1) for line in db.read_text().splitlines() if '=' in line)
 password=env['POSTGRES_PASSWORD']
runtime.write_text('DATABASE_URL=postgresql+psycopg://eventdesk:'+password+'@db/eventdesk\\nEVENTDESK_MODEL_PATH=/models/local-model.joblib\\nEVENTDESK_FIXTURE_MODE=false\\nEVENTDESK_MATERIAL_HOSTS=api.explainingmarkets.ai,df48ooei1lq8t.cloudfront.net\\n')
os.chmod(runtime,0o600)
print(json.dumps({'database_env_mode':oct(db.stat().st_mode&0o777),'runtime_env_mode':oct(runtime.stat().st_mode&0o777)}))
""")
    # SOURCE: host allowlist was read from the authenticated official archive manifest.
    # Validate both listeners before replacing the existing public path. Neither command changes listeners.
    remote_python("""import subprocess,json
commands=[['sudo','docker','run','--rm','-v','/srv/eventdesk/ops/Caddyfile:/etc/caddy/Caddyfile:ro','caddy:2-alpine','caddy','validate','--config','/etc/caddy/Caddyfile','--adapter','caddyfile'],
 ['sudo','docker','run','--rm','--network','eventdesk_default','-v','/srv/eventdesk/ops/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro','haproxy@sha256:5d97434a423c2533cfeb42874d45cf6d69a840b60334582dfbfd5008e94c80be','haproxy','-c','-f','/usr/local/etc/haproxy/haproxy.cfg']]
for command in commands:
 result=subprocess.run(command,capture_output=True)
 if result.returncode: raise RuntimeError('Ingress configuration validation failed; output withheld')
print(json.dumps({'ingress_configuration_validated':True}))
""")
    result = subprocess.run(SSH + ["cd /srv/eventdesk && sudo docker compose -p eventdesk -f compose.production.yaml up --build -d"])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
