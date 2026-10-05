"""Deploy this reviewed source and trusted trained artifact to the existing VPS."""
from __future__ import annotations

import io
import shlex
import subprocess
import tarfile
from pathlib import Path

from bootstrap import SSH
from secret_scan import scan


def remote_python(code: str, data: bytes = b"") -> None:
    result = subprocess.run(SSH + ["sudo python3 -c " + shlex.quote(code)], input=data,
                            capture_output=True)
    if result.returncode:
        raise RuntimeError("Remote deployment step failed; output withheld to protect environment")
    print(result.stdout.decode().strip())


def main() -> None:
    root = Path.cwd()
    if scan(root, Path.home() / ".eventdesk/.env"):
        raise RuntimeError("Secret scan failed")
    model = root / "artifacts/local-model.joblib"
    if not model.is_file():
        raise RuntimeError("Train and evaluate the artifact first")
    files = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"]).decode().splitlines()
    blob = io.BytesIO()
    with tarfile.open(fileobj=blob, mode="w:gz") as archive:
        for name in files:
            if (root / name).is_file():
                archive.add(root / name, arcname=name)
    remote_python("from pathlib import Path; Path('/srv/eventdesk').mkdir(exist_ok=True)")
    result = subprocess.run(SSH + ["sudo tar -xzf - -C /srv/eventdesk --no-same-owner"], input=blob.getvalue())
    if result.returncode:
        raise RuntimeError("Source transfer failed")
    remote_python("""from pathlib import Path
import os,sys,hashlib
directory=Path('/var/lib/eventdesk/models');directory.mkdir(parents=True,exist_ok=True)
raw=sys.stdin.buffer.read();temporary=directory/'model.upload'
temporary.write_bytes(raw);os.chmod(temporary,0o644);os.replace(temporary,directory/'local-model.joblib')
print('model_sha256='+hashlib.sha256(raw).hexdigest())
""", model.read_bytes())
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
    result = subprocess.run(SSH + ["cd /srv/eventdesk && sudo docker compose -p eventdesk -f compose.production.yaml up --build -d"])
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
